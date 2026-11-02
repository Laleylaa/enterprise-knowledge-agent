"""Model construction, bounded requests and observable protocol messages."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import AsyncIterator

from openai import AsyncOpenAI
from pydantic_ai.exceptions import ModelAPIError, ModelConnectionError, ModelHTTPError, ModelRequestTimeout
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelRequest, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.deepseek import DeepSeekProvider

from knowledge_agent.config import Settings
from knowledge_agent.budgets import admit_tools, begin_attempt, begin_model_turn, check_http_capacity, check_time
from knowledge_agent.context import TurnContext
from knowledge_agent.errors import RunStopped
from knowledge_agent.mock_model import create_smoke_model
from knowledge_agent.output_validation import MIXED_OUTPUT_REASON, reject_output
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
        if settings.mock_scenario:
            from knowledge_agent.offline_scenarios import create_scenario_model
            yield create_scenario_model(settings.mock_scenario)
        else:
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
                              settings=OpenAIChatModelSettings(thinking=False, max_tokens=settings.model_output_tokens))


class RecordedModel(WrapperModel):
    """The framework still owns the agent loop; this wrapper owns request policy."""

    def __init__(self, wrapped: Model, state: TurnContext):
        super().__init__(wrapped)
        self.state = state

    async def request(self, messages, model_settings, model_request_parameters):
        state, settings = self.state, self.state.settings
        # Count the full observable payload, including history, tool schemas and observations.
        # UTF-8 bytes plus protocol allowance are a deliberately conservative BPE estimate,
        # not an exact DeepSeek tokenizer count. The configured cap must fit the endpoint.
        payload = {"messages": public_messages(messages),
                   "instructions": [asdict(p) for p in model_request_parameters.instruction_parts or []],
                   "tools": [asdict(t) for t in model_request_parameters.function_tools + model_request_parameters.output_tools]}
        estimated_tokens = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024
        profile_limit = self.wrapped.context_window
        capacity = min(settings.model_context_tokens, profile_limit) if profile_limit else settings.model_context_tokens
        if estimated_tokens + settings.model_output_tokens > capacity:
            state.recorder.event("model_context_rejected", estimated_tokens=estimated_tokens,
                                 estimate_method="utf8_bytes_plus_1024", capacity=capacity,
                                 output_reserve=settings.model_output_tokens)
            raise RunStopped("model_context_limit", "本轮模型上下文超出保守预算；请缩短历史或开始新会话。未截断消息，也未发送本次请求。")
        begin_model_turn(state)
        turn = state.usage.model_turns
        for attempt in range(settings.transport_retries + 1):
            begin_attempt(state)
            request_id = f"{state.recorder.run_id}:M{turn}:A{attempt + 1}"
            state.recorder.append("model-inputs.jsonl", {
                "request_id": request_id, "model_turn": turn, "attempt": attempt + 1,
                "phase": state.phase,
                "messages": public_messages(messages),
                "instructions": [asdict(p) for p in model_request_parameters.instruction_parts or []],
                "tools": [{"name": t.name, "description": t.description, "schema": t.parameters_json_schema}
                          for t in model_request_parameters.function_tools + model_request_parameters.output_tools],
                "settings": {"thinking": False, "stream": False},
            })
            state.evidence.mark_delivered({p.tool_call_id for m in messages if isinstance(m, ModelRequest)
                                           for p in m.parts if isinstance(p, ToolReturnPart)})
            if state.knowledge_tools is not None:
                state.recorder.write("observed-evidence.json", [e.model_dump(mode="json") for e in state.evidence.snapshot()])
            state.recorder.event("model_request_started", origin=settings.mode, request_id=request_id, model_turn=turn, attempt=attempt + 1)
            try:
                async with asyncio.timeout(settings.model_timeout):
                    response = await self.wrapped.request(messages, model_settings, model_request_parameters)
                break
            except (ModelAPIError, TimeoutError) as exc:
                status = exc.status_code if isinstance(exc, ModelHTTPError) else None
                retryable = isinstance(exc, (ModelConnectionError, ModelRequestTimeout, TimeoutError)) or status in {429, 500, 502, 503, 504}
                state.recorder.event("model_request_failed", model_turn=turn, attempt=attempt + 1,
                                     error_type=type(exc).__name__, status_code=status, retryable=retryable)
                if not retryable or attempt >= settings.transport_retries:
                    raise RunStopped("model_request_failed", "模型请求失败且无法继续；请检查服务、凭证或网络。") from exc
                check_http_capacity(state)
                state.recorder.event("model_request_retry", model_turn=turn)
                await asyncio.sleep(0.25)
        check_time(state)
        state.recorder.event("model_response", origin=settings.mode, model_turn=turn,
                             model_name=response.model_name, messages=public_messages([response]))
        calls = [p for p in response.parts if isinstance(p, ToolCallPart)]
        business = [p for p in calls if p.tool_name in BUSINESS_TOOLS]
        output_names = {t.name for t in model_request_parameters.output_tools}
        state.mixed_response = bool(business and any(p.tool_name in output_names for p in calls))
        if state.mixed_response:
            reject_output(state, MIXED_OUTPUT_REASON, "mixed_response")
        for call in business:
            try:
                args = call.args_as_dict()
            except (ValueError, TypeError):
                continue
            if isinstance(args.get("purpose"), str):
                state.action_summaries.append({"model_turn": turn, "tool": call.tool_name,
                                               "tool_call_id": call.tool_call_id, "purpose": args["purpose"]})
        admit_tools(state, business)
        return response
