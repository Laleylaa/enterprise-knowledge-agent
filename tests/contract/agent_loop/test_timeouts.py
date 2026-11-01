"""Cooperative async cancellation, attempt deadlines and whole-turn deadline."""

import asyncio
import json
from contextlib import asynccontextmanager
from time import monotonic

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelConnectionError
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from knowledge_agent import agent as agent_module, budgets, runtime
from knowledge_agent.context import TurnContext
from knowledge_agent.runtime import run_turn
from knowledge_agent.schemas import NonEmpty, RunResult
from knowledge_agent.trace import RunRecorder

pytestmark = pytest.mark.contract


def search():
    return ToolCallPart("search_knowledge", {"query": "差旅", "purpose": "取得原文"}, "search")


def read(call_id):
    return ToolCallPart("read_document", {"doc_id": "D01", "purpose": "核对原文"}, call_id)


@pytest.mark.parametrize("retries", [0, 1])
def test_model_attempt_timeout_cancels_each_attempt_and_bounds_retry(run_loop, retries):
    started, stopped = [], []

    async def respond(messages, info):
        attempt = len(started) + 1
        started.append(attempt)
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(attempt)

    result, records = run_loop(respond, model_timeout=0.02, transport_retries=retries)
    assert result.termination_reason == "model_request_failed"
    assert result.usage.model_turns == 1
    assert started == stopped == list(range(1, retries + 2))
    assert [r["attempt"] for r in records["model-inputs"]] == started
    assert records["tool-results"] == []


def test_tool_timeout_is_observed_without_automatic_tool_retry(run_loop, monkeypatch):
    lifecycle, calls = [], []

    async def read_document(ctx: RunContext[TurnContext], doc_id: NonEmpty, purpose: NonEmpty) -> dict:
        lifecycle.append("started")
        try:
            await asyncio.Event().wait()
            lifecycle.append("late-side-effect")
        finally:
            lifecycle.append("cancelled")

    monkeypatch.setattr(agent_module, "read_document", read_document)

    async def respond(messages, info):
        calls.append(messages)
        if len(calls) == 1:
            return ModelResponse(parts=[read("slow-read")])
        assert len(calls) == 2 and lifecycle == ["started", "cancelled"]
        feedback = next(p.content for p in messages[-1].parts if isinstance(p, ToolReturnPart))
        assert feedback["status"] == "error" and feedback["errors"][0]["code"] == "TOOL_TIMEOUT"
        assert feedback["data"]["segments"] == []
        return ModelResponse(parts=[ToolCallPart("submit_answer", {
            "status": "incomplete", "answer": "读取超时，尚未完成核对。", "citations": [],
            "gaps": ["未取得所需原文。"], "clarification": None,
            "decision_summary": "受控模型观察超时后结束。",
        }, "finish")])

    result, records = run_loop(respond, tool_timeout=0.02)
    assert result.termination_reason == "completed" and result.result.status == "incomplete"
    assert result.result_origin == "mock"  # Preserve the valid model result, not a runtime template.
    assert result.usage.model_turns == 2 and result.usage.tool_calls == 1
    assert len(records["tool-results"]) == 1 and lifecycle == ["started", "cancelled"]


@pytest.mark.parametrize("stage", ["model", "tool", "backoff"])
def test_whole_turn_deadline_stops_work_and_preserves_observed_evidence(
    run_loop, monkeypatch, stage,
):
    calls, stopped, tools = [], [], []

    async def read_document(ctx: RunContext[TurnContext], doc_id: NonEmpty, purpose: NonEmpty) -> dict:
        tools.append(ctx.tool_call_id)
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append("tool")

    monkeypatch.setattr(agent_module, "read_document", read_document)

    async def respond(messages, info):
        calls.append(messages)
        if len(calls) == 1:
            return ModelResponse(parts=[search()])
        assert len(calls) == 2
        if stage == "tool":
            return ModelResponse(parts=[read("active"), read("queued")])
        if stage == "backoff":
            raise ModelConnectionError("local-timeout-test", "injected connection error")
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append("model")

    result, records = run_loop(respond, turn_timeout=0.08, tool_timeout=5, model_timeout=5)
    assert result.termination_reason == "turn_timeout" and result.result.status == "incomplete"
    assert result.usage.model_turns == len(calls) == 2
    assert len(result.observed_evidence) == 1 and result.observed_evidence[0].delivered_to_model
    assert result.result.citations == []
    assert len(records["tool-results"]) == 1
    if stage == "tool":
        assert tools == ["active"] and stopped == ["tool"]
        assert result.usage.tool_calls == 3  # Both second-batch requests were admitted before timeout.
    elif stage == "model":
        assert stopped == ["model"]
    else:
        assert any(e["event_type"] == "model_request_retry" for e in records["trace"])
        assert len(records["model-inputs"]) == 2  # Deadline interrupted backoff before a retry.


def test_initial_snapshot_time_is_inside_whole_turn_deadline(
    loop_environment, run_loop, monkeypatch,
):
    # Advance the monotonic clock during snapshotting, without real sleeps or CPU work.
    now = [monotonic()]
    source = loop_environment[1]
    original = source.snapshot

    def snapshot():
        now[0] += 2
        return original()

    monkeypatch.setattr(source, "snapshot", snapshot)
    monkeypatch.setattr(runtime, "monotonic", lambda: now[0])
    monkeypatch.setattr(budgets, "monotonic", lambda: now[0])

    async def respond(messages, info):
        pytest.fail("No model call may start after the whole-turn deadline")

    result, records = run_loop(respond, turn_timeout=1)
    assert result.termination_reason == "turn_timeout"
    assert result.usage.model_turns == 0 and records["model-inputs"] == []


@pytest.mark.parametrize("stage", ["model", "tool", "backoff"])
def test_cancellation_stops_active_work_saves_evidence_and_closes_model(
    loop_environment, monkeypatch, read_run_records, stage,
):
    settings, source = loop_environment
    lifecycle, model_calls, tool_calls = [], [], []

    async def scenario():
        ready = asyncio.Event()
        original_event = RunRecorder.event

        def record_event(self, event_type, *args, **kwargs):
            original_event(self, event_type, *args, **kwargs)
            if stage == "backoff" and event_type == "model_request_retry":
                ready.set()

        monkeypatch.setattr(RunRecorder, "event", record_event)

        async def read_document(ctx: RunContext[TurnContext], doc_id: NonEmpty, purpose: NonEmpty) -> dict:
            tool_calls.append(ctx.tool_call_id)
            ready.set()
            try:
                await asyncio.Event().wait()
                lifecycle.append("late-side-effect")
            finally:
                lifecycle.append("tool-cancelled")

        monkeypatch.setattr(agent_module, "read_document", read_document)

        async def respond(messages, info):
            model_calls.append(messages)
            if len(model_calls) == 1:
                return ModelResponse(parts=[search()])
            assert len(model_calls) == 2
            if stage == "tool":
                return ModelResponse(parts=[read("active"), read("queued")])
            if stage == "backoff":
                raise ModelConnectionError("local-cancel-test", "injected connection error")
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                lifecycle.append("model-cancelled")

        @asynccontextmanager
        async def factory(config):
            try:
                yield FunctionModel(respond, model_name="scripted-cancellation-contract")
            finally:
                lifecycle.append("closed")

        task = asyncio.create_task(run_turn("国内差旅期限？", settings, source, model_factory=factory))
        try:
            await asyncio.wait_for(ready.wait(), timeout=2)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        await asyncio.sleep(0)  # No queued call or detached task may resume after run_turn exits.

    asyncio.run(scenario())
    outputs = list(settings.output_dir.glob("mock/*/output.json"))
    assert len(outputs) == 1
    result = RunResult.model_validate(json.loads(outputs[0].read_text()))
    records = read_run_records(settings, result)
    assert result.termination_reason == "user_cancelled" and result.result.status == "incomplete"
    assert result.result_origin == "runtime_fallback" and result.result.citations == []
    assert len(result.observed_evidence) == 1 and result.observed_evidence[0].delivered_to_model
    assert len(model_calls) == result.usage.model_turns == 2
    assert len(records["tool-results"]) == 1
    assert lifecycle == ([f"{stage}-cancelled", "closed"] if stage != "backoff" else ["closed"])
    assert tool_calls == (["active"] if stage == "tool" else [])
