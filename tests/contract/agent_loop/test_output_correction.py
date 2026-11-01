"""Output corrections only: schema, citation, mixed response and shared retry allowance."""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from knowledge_agent.runtime import run_turn

pytestmark = pytest.mark.contract


def clarify():
    return {"status": "needs_info", "answer": "请说明费用类型。", "citations": [],
            "gaps": ["费用类型不明。"], "clarification": "请说明费用类型。",
            "decision_summary": "受控模型提交澄清。"}


def search(call_id):
    return ToolCallPart("search_knowledge", {"query": "差旅报销期限", "purpose": "取得依据"},
                        tool_call_id=call_id)


def finish(payload, call_id="answer"):
    return ToolCallPart("submit_answer", payload, tool_call_id=call_id)


def mixed(call_id, *, output_first=False, payload=None):
    parts = [search(call_id), finish(clarify() if payload is None else payload, f"{call_id}-answer")]
    return ModelResponse(parts=parts[::-1] if output_first else parts)


def last_evidence(messages):
    returns = [p for m in messages if isinstance(m, ModelRequest) for p in m.parts
               if isinstance(p, ToolReturnPart) and p.tool_name == "search_knowledge"]
    assert returns
    return returns[-1].content["data"]["hits"][0]


def resolved(evidence):
    return {"status": "resolved", "answer": evidence["text"],
            "citations": [{"doc_id": evidence["doc_id"], "evidence_id": evidence["evidence_id"],
                           "quote": evidence["text"]}],
            "gaps": [], "clarification": None, "decision_summary": "受控模型按实际原文修正。"}


def feedback(messages):
    assert isinstance(messages[-1], ModelRequest)
    parts = [p for p in messages[-1].parts if getattr(p, "tool_name", None) == "submit_answer"]
    assert parts, "The model must actually receive output-rejection feedback"
    return json.dumps([p.content for p in parts], ensure_ascii=False)


def run_script(loop_environment, respond, *, output_retries=2):
    settings, source = loop_environment
    settings = settings.model_copy(update={"output_retries": output_retries})

    @asynccontextmanager
    async def factory(config):
        yield FunctionModel(respond, model_name="scripted-output-correction-contract")

    result = asyncio.run(run_turn("国内差旅报销期限多久？", settings, source, model_factory=factory))
    directory = settings.output_dir / "mock" / result.run_id
    def lines(name):
        path = directory / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    events = lines("trace.jsonl")
    assert events[-1]["event_type"] == "final_result"
    assert result.mode == "mock" and result.usage.http_attempts == 0
    assert json.loads((directory / "output.json").read_text()) == result.model_dump(mode="json")
    return result, events, lines("model-inputs.jsonl"), lines("tool-results.jsonl")


def corrections(events):
    return [e["payload"] for e in events if e["event_type"] == "output_correction_reserved"]


@pytest.mark.parametrize("bad_output", [{"status": "needs_info"}, '{"status":'], ids=["missing_fields", "malformed_json"])
def test_structure_error_is_fed_back_and_corrected(loop_environment, bad_output):
    calls = 0
    async def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[finish(bad_output)])
        assert calls == 2
        assert "answer" in feedback(messages) if isinstance(bad_output, dict) else "json" in feedback(messages).lower()
        return ModelResponse(parts=[finish(clarify(), "corrected")])

    result, events, requests, tools = run_script(loop_environment, respond)
    assert result.termination_reason == "completed" and result.result.status == "needs_info"
    assert len(requests) == 2 and tools == []
    assert [c["kind"] for c in corrections(events)] == ["structure"]


@pytest.mark.parametrize("field,value", [("evidence_id", "other-run:E1"), ("doc_id", "D99"), ("quote", "报销期限为 99 天。")])
def test_citation_error_is_fed_back_and_corrected(loop_environment, field, value):
    calls = 0
    async def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[search("source")])
        answer = resolved(last_evidence(messages))
        if calls == 2:
            answer["citations"][0][field] = value
        else:
            assert calls == 3 and "citations.0" in feedback(messages)
        return ModelResponse(parts=[finish(answer, f"answer-{calls}")])

    result, events, requests, tools = run_script(loop_environment, respond)
    assert result.termination_reason == "completed" and result.result.status == "resolved"
    assert result.result.citations[0].quote == loop_environment[1].get("D01").body
    assert len(requests) == 3 and len(tools) == 1
    assert [c["kind"] for c in corrections(events)] == ["citation"]


@pytest.mark.parametrize("output_first", [False, True], ids=["tool_first", "output_first"])
@pytest.mark.parametrize("malformed", [False, True], ids=["valid_structure", "invalid_structure"])
def test_mixed_response_executes_tool_but_requires_next_model_decision(loop_environment, output_first, malformed):
    calls = 0
    async def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return mixed("mixed-1", output_first=output_first,
                         payload={"status": "needs_info"} if malformed else clarify())
        assert calls == 2 and "本次结果未被接受" in feedback(messages)
        evidence = last_evidence(messages)
        return ModelResponse(parts=[finish(resolved(evidence), "accepted")])

    result, events, requests, tools = run_script(loop_environment, respond)
    assert result.result.status == "resolved" and result.termination_reason == "completed"
    assert len(requests) == 2 and [t["tool_call_id"] for t in tools] == ["mixed-1"]
    assert [c["kind"] for c in corrections(events)] == ["mixed_response"]
    assert result.result.citations[0].evidence_id == result.observed_evidence[0].evidence_id
    parts = [p for m in requests[1]["messages"] for p in m["parts"]]
    assert any(p.get("tool_call_id") == "mixed-1" and p.get("content") == tools[0] for p in parts)
    starts = [e["sequence"] for e in events if e["event_type"] == "model_request_started"]
    tool_event = next(e for e in events if e["event_type"] == "tool_result")
    assert starts[0] < tool_event["sequence"] < starts[1]


@pytest.mark.parametrize("last_is_valid", [False, True], ids=["third_mixed_stops", "third_valid_finishes"])
def test_two_corrections_allow_valid_final_but_no_third_mixed_tools(loop_environment, last_is_valid):
    calls = 0
    async def respond(messages, info):
        nonlocal calls
        calls += 1
        assert calls <= 3
        if calls > 1:
            assert "本次结果未被接受" in feedback(messages)
        if calls == 3 and last_is_valid:
            return ModelResponse(parts=[finish(resolved(last_evidence(messages)), "accepted")])
        return mixed(f"mixed-{calls}")

    result, events, requests, tools = run_script(loop_environment, respond)
    assert len(requests) == calls == 3
    assert [t["tool_call_id"] for t in tools] == ["mixed-1", "mixed-2"]
    assert result.usage.tool_calls == 2
    assert [c["correction"] for c in corrections(events)] == [1, 2]
    assert result.termination_reason == ("completed" if last_is_valid else "output_retry_limit")
    assert result.result.status == ("resolved" if last_is_valid else "incomplete")
    assert len(result.observed_evidence) == 2


def test_zero_corrections_rejects_mixed_before_any_tool(loop_environment):
    async def respond(messages, info):
        return mixed("must-not-execute")
    result, events, requests, tools = run_script(loop_environment, respond, output_retries=0)
    assert result.termination_reason == "output_retry_limit" and result.result.status == "incomplete"
    assert len(requests) == 1 and tools == [] and result.usage.tool_calls == 0
    assert corrections(events) == []


def test_structure_citation_and_mixed_share_allowance_across_tool_success(loop_environment):
    calls = 0
    async def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[finish({"status": "resolved"})])
        if calls == 2:
            assert feedback(messages)
            return ModelResponse(parts=[search("after-structure-error")])
        if calls == 3:
            answer = resolved(last_evidence(messages))
            answer["citations"][0]["quote"] = "错误引文"
            return ModelResponse(parts=[finish(answer, "wrong-citation")])
        assert calls == 4 and "citations.0" in feedback(messages)
        return mixed("must-not-execute")

    result, events, requests, tools = run_script(loop_environment, respond)
    assert result.termination_reason == "output_retry_limit" and result.result.status == "incomplete"
    assert len(requests) == calls == 4
    assert [c["kind"] for c in corrections(events)] == ["structure", "citation"]
    assert [t["tool_call_id"] for t in tools] == ["after-structure-error"]


def test_structure_then_mixed_can_finish_on_last_correction(loop_environment):
    calls = 0
    async def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[finish({"status": "resolved"})])
        if calls == 2:
            assert feedback(messages)
            return mixed("after-structure-error")
        assert calls == 3 and "本次结果未被接受" in feedback(messages)
        return ModelResponse(parts=[finish(resolved(last_evidence(messages)), "accepted")])

    result, events, requests, tools = run_script(loop_environment, respond)
    assert result.termination_reason == "completed" and result.result.status == "resolved"
    assert len(requests) == 3 and len(tools) == 1
    assert [c["kind"] for c in corrections(events)] == ["structure", "mixed_response"]


@pytest.mark.parametrize("error_kind", ["structure", "citation"])
def test_repeated_invalid_output_stops_without_extra_summary(loop_environment, error_kind):
    calls = 0
    async def respond(messages, info):
        nonlocal calls
        calls += 1
        if error_kind == "citation" and calls == 1:
            return ModelResponse(parts=[search("source")])
        if error_kind == "structure":
            answer = {"status": "resolved"}
        else:
            answer = resolved(last_evidence(messages))
            answer["citations"][0]["quote"] = "错误引文"
        return ModelResponse(parts=[finish(answer, f"invalid-{calls}")])

    result, events, requests, tools = run_script(loop_environment, respond)
    assert result.termination_reason == "output_retry_limit" and result.result.status == "incomplete"
    assert len(requests) == calls == (3 if error_kind == "structure" else 4)
    assert [c["kind"] for c in corrections(events)] == [error_kind, error_kind]
    assert len(tools) == (0 if error_kind == "structure" else 1)
