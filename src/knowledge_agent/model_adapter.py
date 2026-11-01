"""Model construction, bounded requests and observable protocol messages."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import AsyncIterator

from openai import AsyncOpenAI
from pydantic_ai.exceptions import ModelAPIError, ModelConnectionError, ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelRequest, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.deepseek import DeepSeekProvider

from knowledge_agent.config import Settings
from knowledge_agent.context import TurnContext
from knowledge_agent.errors import RunStopped
from knowledge_agent.mock_model import create_smoke_model
from knowledge_agent.tools import BUSINESS_TOOLS


def public_messages(messages: list[ModelMessage]) -> list[dict]:
    """Allowlist visible parts; omit thinking, provider metadata and raw errors."""
    serialized = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    visible = {"system-prompt", "user-prompt", "text", "tool-call", "tool-return", "retry-prompt"}
    keys = {"part_kind", "content", "tool_name", "args", "tool_call_id"}
    return [{"kind": message["kind"], "parts": [
        {key: value for key, value in part.items() if key in keys}
        for part in message["parts"] if part["part_kind"] in visible
    ]} for message in serialized]


@asynccontextmanager
async def open_model(settings: Settings) -> AsyncIterator[Model]:
    if settings.mode == "mock":
        yield create_smoke_model()
        return
    if not settings.has_api_key:
        raise RunStopped("missing_api_key", "真实模式缺少 DEEPSEEK_API_KEY，未调用模型，也未切换 Mock。")
    assert settings.deepseek_api_key is not None
    async with AsyncOpenAI(api_key=settings.deepseek_api_key.get_secret_value(),
                           base_url=settings.base_url, max_retries=0,
                           timeout=settings.model_timeout) as client:
        yield OpenAIChatModel(settings.model_name,
                              provider=DeepSeekProvider(openai_client=client),
                              settings=OpenAIChatModelSettings(thinking=False))


class RecordedModel(WrapperModel):
    """The framework still owns the agent loop; this wrapper owns request policy."""

    def __init__(self, wrapped: Model, state: TurnContext):
        super().__init__(wrapped)
        self.state = state

    async def request(self, messages, model_settings, model_request_parameters):
        state, settings = self.state, self.state.settings
        if state.usage.model_turns >= settings.max_model_turns:
            raise RunStopped("model_turn_limit", "达到模型决策轮次上限，处理尚未完成。")
        if state.usage.tool_calls >= settings.max_tool_calls:
            raise RunStopped("tool_call_limit", "达到工具调用上限，处理尚未完成。")
        state.usage.model_turns += 1
        turn = state.usage.model_turns
        for attempt in range(settings.transport_retries + 1):
            if settings.mode == "real":
                if state.usage.http_attempts >= settings.max_http_attempts:
                    raise RunStopped("http_attempt_limit", "达到模型请求尝试上限。")
                state.usage.http_attempts += 1
            state.recorder.append("model-inputs.jsonl", {
                "model_turn": turn, "attempt": attempt + 1,
                "messages": public_messages(messages),
                "instructions": [asdict(p) for p in model_request_parameters.instruction_parts or []],
                "tools": [{"name": t.name, "description": t.description, "schema": t.parameters_json_schema}
                          for t in model_request_parameters.function_tools + model_request_parameters.output_tools],
                "settings": {"thinking": False, "stream": False},
            })
            state.evidence.mark_delivered({p.tool_call_id for m in messages if isinstance(m, ModelRequest)
                                           for p in m.parts if isinstance(p, ToolReturnPart)})
            state.recorder.event("model_request_started", origin=settings.mode, model_turn=turn, attempt=attempt + 1)
            try:
                async with asyncio.timeout(settings.model_timeout):
                    response = await self.wrapped.request(messages, model_settings, model_request_parameters)
                break
            except (ModelAPIError, TimeoutError) as exc:
                status = exc.status_code if isinstance(exc, ModelHTTPError) else None
                retryable = isinstance(exc, (ModelConnectionError, TimeoutError)) or status in {429, 500, 502, 503, 504}
                state.recorder.event("model_request_failed", model_turn=turn, attempt=attempt + 1,
                                     error_type=type(exc).__name__, status_code=status, retryable=retryable)
                if not retryable or attempt >= settings.transport_retries:
                    raise RunStopped("model_request_failed", "模型请求失败且无法继续；请检查服务、凭证或网络。") from exc
                state.recorder.event("model_request_retry", model_turn=turn)
                await asyncio.sleep(0.25)
        state.recorder.event("model_response", origin=settings.mode, model_turn=turn,
                             model_name=response.model_name, messages=public_messages([response]))
        calls = [p for p in response.parts if isinstance(p, ToolCallPart)]
        business = [p for p in calls if p.tool_name in BUSINESS_TOOLS]
        output_names = {t.name for t in model_request_parameters.output_tools}
        state.mixed_response = bool(business and any(p.tool_name in output_names for p in calls))
        if business and state.usage.model_turns >= settings.max_model_turns:
            raise RunStopped("model_turn_limit", "没有剩余模型轮次观察新工具结果，处理尚未完成。")
        for call in business:
            if state.usage.tool_calls >= settings.max_tool_calls:
                raise RunStopped("tool_call_limit", "达到工具调用上限，处理尚未完成。")
            state.usage.tool_calls += 1
            state.recorder.event("tool_requested", origin=settings.mode, model_turn=turn,
                                 tool=call.tool_name, tool_call_id=call.tool_call_id, arguments=call.args)
        return response
