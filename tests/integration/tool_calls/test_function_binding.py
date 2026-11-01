"""Standard function definitions and actual local tool dispatch; no final-answer assertions."""

import asyncio
import json

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.tools import GenerateToolJsonSchema

from knowledge_agent.reading.tool import ReadRequest, ReadTool
from knowledge_agent.retrieval.tool import SearchRequest, SearchTool
from tests.support.tool_calls import acknowledgement, drive_tool_exchange, observations, records

pytestmark = pytest.mark.contract


def assert_definitions(info):
    tools = {t.name: t for t in info.function_tools}
    assert set(tools) == {"search_knowledge", "read_document"}
    for name, contract, description in [("search_knowledge", SearchRequest, SearchTool.description),
                                         ("read_document", ReadRequest, ReadTool.description)]:
        tool = tools[name]
        schema = tool.parameters_json_schema
        expected = contract.model_json_schema(schema_generator=GenerateToolJsonSchema)
        assert tool.description == description
        assert schema["properties"] == expected["properties"]
        assert schema["required"] == expected["required"]
        assert schema["additionalProperties"] is False
        assert "ctx" not in schema["properties"] and "request" not in schema["properties"]
        assert "call_id" not in schema["properties"]
        assert all(field.get("description") for field in schema["properties"].values())
    assert [t.name for t in info.output_tools] == ["submit_answer"]


def execute(state, respond, requests):
    async def checked(messages, info):
        assert_definitions(info)  # Definitions must be present on every request, including observations.
        return respond(messages, info)
    model = FunctionModel(checked, model_name="scripted-function-call-integration")
    result = asyncio.run(drive_tool_exchange(state, model, requests=requests, origin="scripted_function_model"))
    events = records(state, "trace")
    returns = records(state, "tool-results")
    inputs = records(state, "model-inputs")
    assert not any(e["event_type"] == "final_result" for e in events)
    assert all(e.delivered_to_model for e in state.evidence.snapshot())
    assert json.loads((state.recorder.directory / "input.json").read_text())["question"] == "请查询差旅报销相关制度原文。"
    assert json.loads((state.recorder.directory / "input.json").read_text())["config"]["retrieval"] == "bm25"
    for returned in returns:
        starts = [e for e in events if e["event_type"] == "tool_started" and e["payload"]["tool_call_id"] == returned["tool_call_id"]]
        ends = [e for e in events if e["event_type"] == "tool_result" and e["payload"]["tool_call_id"] == returned["tool_call_id"]]
        assert len(starts) == len(ends) == 1  # Execution policy owns starts, backend owns results.
        assert starts[0]["sequence"] < ends[0]["sequence"]
        assert any(p.get("part_kind") == "tool-return" and p.get("tool_call_id") == returned["tool_call_id"]
                   and p["content"] == returned for row in inputs[1:] for m in row["messages"] for p in m["parts"])
    assert result["usage"]["model_turns"] == requests
    return result


@pytest.mark.parametrize("args,expected_doc", [
    ({"query": "国内差旅报销期限", "purpose": "查找条款", "limit": 1}, "D01"),
    ({"query": "", "purpose": "按文档线索定位", "doc_ids": ["D02"]}, "D02"),
], ids=["keyword_search", "explicit_id"])
def test_model_calls_real_search_with_public_arguments(bound_state, args, expected_doc):
    state = bound_state(f"fc_search_{expected_doc}", "F2_conflicting_rules")
    def respond(messages, info):
        returned = observations(messages)
        if not returned:
            # FC arguments as JSON, like a provider response, not a direct Python execute call.
            return ModelResponse(parts=[ToolCallPart("search_knowledge", json.dumps(args), "fc-search")])
        latest = returned[-1]
        assert latest.tool_name == "search_knowledge" and latest.tool_call_id == "fc-search"
        assert latest.content["status"] == "ok"
        assert latest.content["data"]["hits"][0]["doc_id"] == expected_doc
        assert latest.content["execution"]["strategy"] == ("bm25" if args["query"] else "id_lookup")
        return acknowledgement()
    result = execute(state, respond, 2)
    assert result["usage"]["tool_calls"] == 1


@pytest.mark.parametrize("selector,strategy", [({}, "document"), ({"section_id": "D01-S0003"}, "section"),
                                               ({"chunk_id": "D01-C0003"}, "chunk")])
def test_model_calls_each_read_scope_without_forced_search(bound_state, selector, strategy):
    state = bound_state(f"fc_read_{strategy}")
    def respond(messages, info):
        returned = observations(messages)
        if not returned:
            return ModelResponse(parts=[ToolCallPart("read_document", json.dumps({
                "doc_id": "D01", "purpose": "核实原文", **selector}), "fc-read")])
        value = returned[-1].content
        assert value["status"] == "ok" and value["execution"]["strategy"] == strategy
        for segment in value["data"]["segments"]:
            span = segment["source_span"]
            assert segment["text"] == state.source.retrieval_snapshot.get("D01").body[span["start"]:span["end"]]
        assert value["execution"]["requested_mode"] is None
        return acknowledgement()
    result = execute(state, respond, 2)
    assert [r["tool"] for r in result["tool_results"]] == ["read_document"]


def test_model_uses_returned_section_locator_for_expansion(bound_state):
    state = bound_state("fc_search_read_section", "R1_section_context")
    def respond(messages, info):
        returned = observations(messages)
        if not returned:
            return ModelResponse(parts=[ToolCallPart("search_knowledge", {
                "query": "草稿保存时间", "purpose": "查找提交条款", "limit": 1}, "fc-search")])
        if len(returned) == 1:
            hit = returned[0].content["data"]["hits"][0]
            assert "仅适用于国内差旅" not in hit["text"]
            return ModelResponse(parts=[ToolCallPart("read_document", {
                "doc_id": hit["doc_id"], "section_id": hit["section_id"], "purpose": "扩大到所属章节核实条件"}, "fc-section")])
        assert "仅适用于国内差旅" in returned[-1].content["data"]["segments"][0]["text"]
        assert returned[0].content["corpus_hash"] == returned[-1].content["corpus_hash"]
        return acknowledgement()
    execute(state, respond, 3)
    assert state.knowledge_tools.search.evidence is state.knowledge_tools.reader.evidence is state.evidence
    assert state.knowledge_tools.search.index.snapshot is state.knowledge_tools.reader.snapshot
    assert {e.tool_call_id for e in state.evidence.snapshot()} == {"fc-search", "fc-section"}


def test_model_continues_search_cursor_in_same_tool_instance(bound_state):
    state = bound_state("fc_search_pagination")
    def respond(messages, info):
        returned = observations(messages)
        args = {"query": "", "doc_ids": ["D01"], "limit": 1, "purpose": "按来源顺序取块"}
        if not returned:
            return ModelResponse(parts=[ToolCallPart("search_knowledge", args, "fc-page-1")])
        if len(returned) == 1:
            cursor = returned[-1].content["execution"]["next_cursor"]
            assert cursor
            return ModelResponse(parts=[ToolCallPart("search_knowledge", {**args, "cursor": cursor}, "fc-page-2")])
        ids = [r.content["data"]["hits"][0]["chunk_id"] for r in returned]
        assert ids == [c.chunk_id for c in state.source.retrieval_snapshot.chunks[:2]]
        return acknowledgement()
    execute(state, respond, 3)


def test_model_uses_read_locator_arguments_to_obtain_successful_chunk(bound_state):
    state = bound_state("fc_read_local_locator", "R1_section_context", max_tool_chars=340)
    def respond(messages, info):
        returned = observations(messages)
        if not returned:
            return ModelResponse(parts=[ToolCallPart("read_document", {
                "doc_id": "D10", "section_id": "D10-S0002", "purpose": "读取提交章节"}, "fc-too-large")])
        if len(returned) == 1:
            result = returned[0].content
            assert result["errors"][0]["code"] == "CONTENT_TOO_LARGE" and not state.evidence.snapshot()
            args = result["data"]["locators"][0]["read_args"]
            return ModelResponse(parts=[ToolCallPart("read_document", {**args, "purpose": "读取可容纳的局部原文"}, "fc-local")])
        assert returned[-1].content["status"] == "ok" and returned[-1].content["execution"]["strategy"] == "chunk"
        return acknowledgement()
    execute(state, respond, 3)


def test_same_response_can_call_both_tools_with_correct_ids(bound_state):
    state = bound_state("fc_two_tools_one_response")
    def respond(messages, info):
        returned = observations(messages)
        if not returned:
            return ModelResponse(parts=[
                ToolCallPart("search_knowledge", {"query": "期限", "purpose": "查条款"}, "fc-search"),
                ToolCallPart("read_document", {"doc_id": "D01", "purpose": "读取文档"}, "fc-read")])
        assert [(r.tool_name, r.tool_call_id) for r in returned] == [("search_knowledge", "fc-search"), ("read_document", "fc-read")]
        assert all(r.content["status"] == "ok" and r.content["tool_call_id"] == r.tool_call_id for r in returned)
        return acknowledgement()
    result = execute(state, respond, 2)
    assert result["usage"]["tool_calls"] == 2


@pytest.mark.parametrize("name,bad,good", [
    ("search_knowledge", {"query": "期限", "purpose": "查找", "limit": 0}, {"query": "期限", "purpose": "查找", "limit": 1}),
    ("search_knowledge", {"query": "", "purpose": "定位", "doc_ids": []}, {"query": "", "purpose": "定位", "doc_ids": ["D01"]}),
    ("read_document", {"doc_id": "D01", "purpose": "读取", "section_id": "D01-S0001", "chunk_id": "D01-C0001"},
     {"doc_id": "D01", "purpose": "读取", "chunk_id": "D01-C0001"}),
], ids=["limit", "empty_ids", "exclusive_read_selector"])
def test_framework_validates_arguments_before_dispatch_then_accepts_correction(bound_state, name, bad, good):
    state = bound_state(f"fc_argument_correction_{'limit' if 'limit' in bad else 'ids' if 'doc_ids' in bad else 'selector'}")
    count = 0
    def respond(messages, info):
        nonlocal count
        count += 1
        if count == 1:
            return ModelResponse(parts=[ToolCallPart(name, json.dumps(bad), "fc-invalid")])
        if count == 2:
            feedback = next(p for p in messages[-1].parts if isinstance(p, ToolReturnPart) and p.tool_call_id == "fc-invalid")
            assert isinstance(feedback.content, list) and feedback.content[0]["type"]
            assert records(state, "tool-results") == [] and state.evidence.snapshot() == []
            return ModelResponse(parts=[ToolCallPart(name, json.dumps(good), "fc-corrected")])
        assert observations(messages)[-1].content["status"] == "ok"
        return acknowledgement()
    result = execute(state, respond, 3)
    assert result["usage"]["tool_calls"] == 2  # Accepted invalid arguments consume an attempt.
    assert [r["tool_call_id"] for r in result["tool_results"]] == ["fc-corrected"]
