"""Cancellable tool execution using public PydanticAI capability hooks."""

import asyncio
from typing import Any

from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability, RawToolArgs, ValidatedToolArgs, WrapToolExecuteHandler
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from knowledge_agent.budgets import begin_tool, check_time
from knowledge_agent.context import TurnContext
from knowledge_agent.tools import tool_error


class ToolExecutionPolicy(AbstractCapability[TurnContext]):
    async def on_tool_validate_error(
        self, ctx: RunContext[TurnContext], *, call: ToolCallPart, tool_def: ToolDefinition,
        args: RawToolArgs, error: ValidationError | ModelRetry,
    ) -> ValidatedToolArgs:
        ctx.deps.recorder.event("tool_arguments_rejected", tool=call.tool_name,
                                tool_call_id=call.tool_call_id, error_type=type(error).__name__)
        raise error  # The framework supplies parameter feedback, not a fabricated observation.

    async def wrap_tool_execute(
        self, ctx: RunContext[TurnContext], *, call: ToolCallPart, tool_def: ToolDefinition,
        args: ValidatedToolArgs, handler: WrapToolExecuteHandler,
    ) -> Any:
        state = ctx.deps
        begin_tool(state, call)
        state.recorder.event("tool_started", tool=call.tool_name,
                             tool_call_id=call.tool_call_id, arguments=call.args)
        timeout = asyncio.timeout(state.settings.tool_timeout)
        try:
            async with timeout:
                result = await handler(args)
            check_time(state)
            return result
        except TimeoutError:
            if not timeout.expired():
                raise  # A backend's own TimeoutError is not this execution deadline.
            check_time(state)  # The whole-turn deadline always wins over recovery.
            return tool_error(ctx, call.tool_name, "TOOL_TIMEOUT", "工具执行超时，可在预算内调整或重试。")
        except asyncio.CancelledError:
            state.recorder.event("tool_cancelled", tool=call.tool_name, tool_call_id=call.tool_call_id)
            raise
