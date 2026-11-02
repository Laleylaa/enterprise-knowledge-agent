"""Admission/counting boundaries only; no business acceptance assertions."""

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

pytestmark = pytest.mark.boundary


def search(call_id):
    return ToolCallPart("search_knowledge", {"query": "差旅", "purpose": "获取依据"}, call_id)


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
