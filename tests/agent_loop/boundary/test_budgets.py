"""Admission/counting boundaries only; no business acceptance assertions."""

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

pytestmark = pytest.mark.boundary


def search(call_id):
    return ToolCallPart("search_knowledge", {"query": "差旅", "purpose": "获取依据"}, call_id)


def clarify():
    return ToolCallPart("submit_answer", {
        "status": "needs_info", "answer": "请说明费用类型。", "citations": [],
        "gaps": ["费用类型不明。"], "clarification": "请说明费用类型。",
        "decision_summary": "受控模型提交澄清。",
    }, "finish")


@pytest.mark.parametrize("final", [True, False], ids=["last_turn_final", "last_turn_needs_tool"])
def test_last_model_turn_accepts_only_final(run_loop, final):
    calls = 0

    async def respond(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[clarify() if final else search("search")])

    result, records = run_loop(respond, max_model_turns=1)
    assert calls == result.usage.model_turns == 1
    assert result.usage.tool_calls == 0
    assert result.termination_reason == ("completed" if final else "model_turn_limit")
    assert result.result.status == ("needs_info" if final else "incomplete")
    assert records["tool-results"] == []


@pytest.mark.parametrize("limit", ["model", "tool"])
def test_repeated_legal_requests_stop_without_summary_and_keep_evidence(run_loop, limit):
    calls = 0

    async def respond(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[search(f"search-{calls}")])

    result, records = run_loop(respond, **({"max_model_turns": 2} if limit == "model" else {"max_tool_calls": 1}))
    assert result.termination_reason == ("model_turn_limit" if limit == "model" else "tool_call_limit")
    assert result.result.status == "incomplete" and result.result.citations == []
    assert result.usage.model_turns == calls == (2 if limit == "model" else 1)
    assert result.usage.tool_calls == len(records["tool-results"]) == 1
    assert len(result.observed_evidence) == 1
    assert result.observed_evidence[0].delivered_to_model == (limit == "model")
    assert any(e["event_type"] == "budget_blocked" for e in records["trace"])


@pytest.mark.parametrize("capacity", [1, 2], ids=["batch_rejected", "batch_admitted_at_limit"])
def test_batch_admission_is_atomic_and_execution_is_serial(run_loop, capacity):
    async def respond(messages, info):
        return ModelResponse(parts=[search("first"), search("second")])

    result, records = run_loop(respond, max_tool_calls=capacity)
    expected = 0 if capacity == 1 else 2
    assert result.termination_reason == "tool_call_limit"
    assert result.usage.model_turns == 1 and result.usage.tool_calls == expected
    assert len(records["tool-results"]) == expected
    actions = [(e["event_type"], e["payload"]["tool_call_id"]) for e in records["trace"]
               if e["event_type"] in {"tool_started", "tool_result"}]
    assert actions == ([] if not expected else [
        ("tool_started", "first"), ("tool_result", "first"),
        ("tool_started", "second"), ("tool_result", "second"),
    ])


def test_repeated_failed_and_invalid_calls_all_count_but_output_does_not(run_loop):
    calls = 0

    async def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[
                search("same-args-1"), search("same-args-2"),
                ToolCallPart("read_document", {"doc_id": "missing", "purpose": "读取依据"}, "missing"),
                ToolCallPart("read_document", {"purpose": "缺少参数"}, "bad-args"),
            ])
        assert calls == 2
        feedback = next(p for p in messages[-1].parts
                        if isinstance(p, ToolReturnPart) and p.tool_call_id == "bad-args")
        assert list(feedback.content[0]["loc"]) == ["doc_id"]
        return ModelResponse(parts=[clarify()])

    result, records = run_loop(respond, max_tool_calls=5)
    assert result.termination_reason == "completed"
    assert result.usage.model_turns == 2 and result.usage.tool_calls == 4
    assert [r["status"] for r in records["tool-results"]] == ["ok", "ok", "error"]
    assert records["tool-results"][-1]["errors"][0]["code"] == "NOT_FOUND"
    started = [e["payload"]["tool_call_id"] for e in records["trace"] if e["event_type"] == "tool_started"]
    assert started == ["same-args-1", "same-args-2", "missing"]
    assert len([e for e in records["trace"] if e["event_type"] == "tool_arguments_rejected"]) == 1


def test_bad_tool_parameters_at_limit_do_not_trigger_extra_model_call(run_loop):
    async def respond(messages, info):
        return ModelResponse(parts=[ToolCallPart("read_document", {"purpose": "缺少参数"}, "bad")])

    result, records = run_loop(respond, max_tool_calls=1)
    assert result.termination_reason == "tool_call_limit"
    assert result.usage.model_turns == result.usage.tool_calls == 1
    assert records["tool-results"] == []
