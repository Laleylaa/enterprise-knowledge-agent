"""Run-scoped admission checks, independent of framework usage counters."""

from time import monotonic
from typing import NoReturn

from pydantic_ai.messages import ToolCallPart

from knowledge_agent.context import TurnContext
from knowledge_agent.errors import RunStopped


def stop(state: TurnContext, reason: str, message: str) -> NoReturn:
    state.recorder.event("budget_blocked", reason=reason, usage=state.usage.model_dump())
    raise RunStopped(reason, message)


def check_time(state: TurnContext) -> None:
    if monotonic() >= state.deadline:
        stop(state, "turn_timeout", "达到整轮时间上限，处理尚未完成。")


def check_http_capacity(state: TurnContext) -> None:
    if state.settings.mode == "real" and state.usage.http_attempts >= state.settings.max_http_attempts:
        stop(state, "http_attempt_limit", "达到模型请求尝试上限，处理尚未完成。")


def check_model_capacity(state: TurnContext) -> None:
    if state.usage.model_turns >= state.settings.max_model_turns:
        stop(state, "model_turn_limit", "没有剩余模型轮次继续处理或观察工具结果。")
    check_http_capacity(state)


def begin_model_turn(state: TurnContext) -> None:
    check_time(state)
    if state.usage.tool_calls >= state.settings.max_tool_calls:
        stop(state, "tool_call_limit", "达到工具调用上限，处理尚未完成。")
    check_model_capacity(state)
    state.usage.model_turns += 1


def begin_attempt(state: TurnContext) -> None:
    check_time(state)
    check_http_capacity(state)
    if state.settings.mode == "real":
        state.usage.http_attempts += 1


def admit_tools(state: TurnContext, calls: list[ToolCallPart]) -> None:
    """Admit a complete batch or none; invalid args still consume admitted slots.

    The framework validates a batch before executing its serial tools. Rejecting
    an oversized batch up front avoids charging an unexecuted prefix. Once
    admitted, every request is charged, including failed/invalid/repeated calls.
    """
    state.pending_tools.clear()
    if not calls:
        return
    check_time(state)
    check_model_capacity(state)  # Reserve the possibility of observing these results.
    if len(calls) > state.settings.max_tool_calls - state.usage.tool_calls:
        stop(state, "tool_call_limit", "本批工具请求超过剩余额度，整批未接纳，处理尚未完成。")
    for call in calls:
        state.usage.tool_calls += 1
        state.pending_tools.add((call.tool_call_id, call.tool_name))
        state.recorder.event("tool_requested", origin=state.settings.mode,
                             model_turn=state.usage.model_turns, tool=call.tool_name,
                             tool_call_id=call.tool_call_id, arguments=call.args)


def begin_tool(state: TurnContext, call: ToolCallPart) -> None:
    check_time(state)
    check_model_capacity(state)
    reservation = (call.tool_call_id, call.tool_name)
    if reservation not in state.pending_tools:
        raise RunStopped("tool_not_admitted", "工具请求未获接纳，处理尚未完成。")
    state.pending_tools.remove(reservation)
