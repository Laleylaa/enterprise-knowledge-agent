"""Only normal continuation and termination; scripted models, actual local tools."""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from knowledge_agent.runtime import run_turn

pytestmark = pytest.mark.contract


def execute(loop_environment, question, respond):
    settings, source = loop_environment

    @asynccontextmanager
    async def model_factory(config):
        assert config is settings
        yield FunctionModel(respond, model_name="scripted-normal-loop-contract")

    result = asyncio.run(run_turn(question, settings, source, model_factory=model_factory))
    directory = settings.output_dir / "mock" / result.run_id
    events = [json.loads(line) for line in (directory / "trace.jsonl").read_text().splitlines()]
    requests = [json.loads(line) for line in (directory / "model-inputs.jsonl").read_text().splitlines()]
    assert result.termination_reason == "completed"
    assert result.result_origin == "mock"
    assert result.usage.http_attempts == 0
    assert events[-1]["event_type"] == "final_result"
    assert sum(e["event_type"] == "final_result" for e in events) == 1
    assert sum(e["event_type"] == "model_response" for e in events) == len(requests)
    assert json.loads((directory / "output.json").read_text()) == result.model_dump(mode="json")
    return result, events, requests, directory


@pytest.mark.parametrize("read_again", [False, True], ids=["search_then_finish", "search_read_then_finish"])
def test_observe_tool_results_then_continue_or_finish(loop_environment, read_again):
    observed = []

    async def respond(messages, info):
        # Decisions consume the actual observation supplied by PydanticAI, not a
        # prebuilt evidence ID or a tool result fabricated by the test driver.
        returns = [p for m in messages if isinstance(m, ModelRequest)
                   for p in m.parts if isinstance(p, ToolReturnPart)]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("search_knowledge", {
                "query": "国内差旅报销期限", "purpose": "取得本轮原文",
            }, tool_call_id="search-1")])
        latest = returns[-1]
        result = latest.content
        assert isinstance(result, dict) and result["status"] == "ok"
        assert latest.tool_call_id == result["tool_call_id"]
        key = "hits" if latest.tool_name == "search_knowledge" else "segments"
        evidence = result["data"][key][0]
        observed.append((latest.tool_call_id, evidence))
        if read_again and latest.tool_name == "search_knowledge":
            return ModelResponse(parts=[ToolCallPart("read_document", {
                "doc_id": evidence["doc_id"], "purpose": "依据搜索返回的 ID 读取原文",
            }, tool_call_id="read-1")])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "status": "resolved", "answer": evidence["text"],
            "citations": [{"evidence_id": evidence["evidence_id"],
                           "doc_id": evidence["doc_id"], "quote": evidence["text"]}],
            "gaps": [], "clarification": None,
            "decision_summary": "受控测试模型根据实际工具结果提交终态。",
        }, tool_call_id="finish-1")])

    result, events, requests, directory = execute(loop_environment, "国内差旅报销期限多久？", respond)
    expected_ids = ["search-1", "read-1"] if read_again else ["search-1"]
    assert [call_id for call_id, _ in observed] == expected_ids
    assert result.result.status == "resolved"
    assert result.result.answer == loop_environment[1].get("D01").body
    assert result.result.citations[0].evidence_id == observed[-1][1]["evidence_id"]
    assert result.usage.model_turns == len(expected_ids) + 1
    assert len(requests) == len(expected_ids) + 1  # No model request after the valid final answer.
    assert [e["payload"]["tool_call_id"] for e in events if e["event_type"] == "tool_started"] == expected_ids
    assert all(e.delivered_to_model for e in result.observed_evidence)
    tool_records = [json.loads(line) for line in (directory / "tool-results.jsonl").read_text().splitlines()]
    for index, call_id in enumerate(expected_ids):
        parts = [p for m in requests[index + 1]["messages"] for p in m["parts"]]
        returned = next(p for p in parts if p["part_kind"] == "tool-return" and p["tool_call_id"] == call_id)
        assert returned["content"] == tool_records[index]
        tool_event = next(e for e in events if e["event_type"] == "tool_result" and e["payload"]["tool_call_id"] == call_id)
        next_request = next(e for e in events if e["event_type"] == "model_request_started" and e["payload"]["model_turn"] == index + 2)
        assert tool_event["sequence"] < next_request["sequence"]


def test_clarification_can_finish_without_tools(loop_environment):
    clarification = "请问你指的是什么费用？"

    async def respond(messages, info):
        assert not any(isinstance(p, ToolReturnPart) for m in messages if isinstance(m, ModelRequest)
                       for p in m.parts)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "status": "needs_info", "answer": clarification, "citations": [],
            "gaps": ["费用类型尚不明确。"], "clarification": clarification,
            "decision_summary": "受控测试模型直接请求必要信息。",
        }, tool_call_id="clarify-1")])

    result, events, requests, directory = execute(loop_environment, "这个能报销吗？", respond)
    assert result.result.status == "needs_info" and result.result.clarification == clarification
    assert result.observed_evidence == [] and result.result.citations == []
    assert result.usage.model_turns == 1 and result.usage.tool_calls == 0
    assert len(requests) == 1
    assert not any(e["event_type"].startswith("tool_") for e in events)
    assert not (directory / "tool-results.jsonl").exists()
