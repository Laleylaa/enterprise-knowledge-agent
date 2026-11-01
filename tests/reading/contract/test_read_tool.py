"""Public selectors, exact sources, shared search IDs, evidence and failures."""

import json
import pytest

from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.reading.tool import ReadRequest, ReadTool
from knowledge_agent.schemas import Answer

pytestmark = pytest.mark.contract


def read(tool, **args):
    return tool.execute({"doc_id": "D01", "purpose": "核对读取契约", **args}, call_id="contract-read")


@pytest.mark.parametrize("args", [
    {"doc_id": ""}, {"doc_id": " "}, {"doc_id": 1}, {"purpose": "\t"},
    {"section_id": ""}, {"chunk_id": " "}, {"cursor": 1}, {"extra": 1},
    {"section_id": "D01-S0001", "chunk_id": "D01-C0001"},
])
def test_invalid_arguments_do_not_access_source(reader_factory, monkeypatch, args):
    tool = reader_factory()
    monkeypatch.setattr(tool, "_select", lambda *_: pytest.fail("Invalid arguments cannot read source"))
    result = read(tool, **args)
    assert result["errors"][0]["code"] == "INVALID_ARGUMENT"
    assert result["data"] == {"hits": [], "segments": [], "locators": []}
    assert tool.evidence.snapshot() == []


def test_public_schema_has_only_model_arguments():
    schema = ReadRequest.model_json_schema()
    assert set(schema["properties"]) == {"doc_id", "purpose", "section_id", "chunk_id", "cursor"}
    assert set(schema["required"]) == {"doc_id", "purpose"}
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("args,code,kind", [
    ({"doc_id": "missing"}, "NOT_FOUND", "doc"),
    ({"section_id": "missing"}, "NOT_FOUND", "section"),
    ({"chunk_id": "missing"}, "NOT_FOUND", "chunk"),
    ({"section_id": "D02-S0001"}, "INVALID_ARGUMENT", "section"),
    ({"chunk_id": "D02-C0001"}, "INVALID_ARGUMENT", "chunk"),
])
def test_missing_and_foreign_selectors_are_distinct(reader_factory, args, code, kind):
    tool = reader_factory("F2_conflicting_rules")
    result = read(tool, **args)
    assert result["status"] == "error" and result["errors"][0]["code"] == code
    assert result["errors"][0]["target"]["kind"] == kind
    assert result["errors"][0]["retryable"] is False
    assert tool.evidence.snapshot() == []


@pytest.mark.parametrize("strategy", ["document", "section", "chunk"])
def test_all_read_modes_return_exact_spans_and_shared_envelope(reader_factory, strategy):
    tool = reader_factory()
    document = tool.snapshot.get("D01")
    section = list(tool.snapshot.sections.values())[2]
    chunk = next(c for c in tool.snapshot.chunks if c.section_id == section.section_id)
    args = {"section_id": section.section_id} if strategy == "section" else {"chunk_id": chunk.chunk_id} if strategy == "chunk" else {}
    result = read(tool, **args)
    assert set(result) == {"schema_version", "tool", "tool_call_id", "corpus_hash", "status", "data", "errors", "execution"}
    assert result["execution"] == {"strategy": strategy, "requested_mode": None, "effective_branches": [],
                                   "next_cursor": None, "has_more": False, "return_limited": False}
    segments = result["data"]["segments"]
    expected = document.body if strategy == "document" else document.body[section.start:section.end] if strategy == "section" else chunk.text
    assert "".join(s["text"] for s in segments) == expected
    items = {e.evidence_id: e for e in tool.evidence.snapshot()}
    for segment in segments:
        span = segment["source_span"]
        assert segment["text"] == document.body[span["start"]:span["end"]]
        evidence = items[segment["evidence_id"]]
        assert evidence.tool_call_id == "contract-read" and evidence.corpus_hash == result["corpus_hash"]
        assert segment["content_hash"] == evidence.content_hash
        assert segment["version_date"] == document.version_date.isoformat()
        assert not evidence.delivered_to_model
        assert all(s.text == document.body[s.start:s.end] for s in evidence.source_spans)


def test_search_locations_and_evidence_are_compatible_without_agent(tool_factory):
    search = tool_factory()
    hits = search.execute({"query": "期限", "purpose": "提供定位"}, call_id="search")["data"]["hits"]
    reader = ReadTool(search.index.snapshot, search.settings, search.evidence, search.recorder)
    for hit in hits:
        result = reader.execute({"doc_id": hit["doc_id"], "chunk_id": hit["chunk_id"], "purpose": "读取命中块"}, call_id="read-" + hit["chunk_id"])
        segment = result["data"]["segments"][0]
        assert {k: v for k, v in segment.items() if k != "evidence_id"} == {k: v for k, v in hit.items() if k != "evidence_id"}
        assert segment["evidence_id"] != hit["evidence_id"]
        assert read(reader, section_id=hit["section_id"])["status"] == "ok"


def test_reader_rejects_a_foreign_evidence_snapshot(reader_factory):
    reader = reader_factory()
    with pytest.raises(ValueError, match="same snapshot"):
        ReadTool(reader.snapshot, reader.settings, EvidenceStore("other", "foreign"), reader.recorder)


def test_detached_heading_cannot_be_fused_and_unobserved_quote_is_rejected(reader_factory):
    tool = reader_factory("R1_section_context")
    chunk = next(c for c in tool.snapshot.chunks if c.heading_span and c.start > c.heading_span.end)
    result = read(tool, doc_id="D10", chunk_id=chunk.chunk_id)
    segment = result["data"]["segments"][0]
    def answer(quote):
        return Answer(status="resolved", answer="受控引用校验", gaps=[], clarification=None,
                      decision_summary="只核对引用契约", citations=[{
                          "doc_id": "D10", "evidence_id": segment["evidence_id"], "quote": quote}])
    with pytest.raises(ValueError, match="反馈"):
        tool.evidence.validate(answer(chunk.text))
    # Simulate delivery for validator checks only; no model/Agent is invoked.
    tool.evidence.mark_delivered({"contract-read"})
    tool.evidence.validate(answer(chunk.text))
    tool.evidence.validate(answer(segment["section_heading"]))
    with pytest.raises(ValueError):
        tool.evidence.validate(answer(segment["section_heading"] + chunk.text))


def test_purpose_only_changes_records_and_all_calls_are_retained(reader_factory):
    tool = reader_factory()
    first = read(tool, purpose="读全文")
    second = read(tool, purpose="核实适用条件")
    assert [s["text"] for s in first["data"]["segments"]] == [s["text"] for s in second["data"]["segments"]]
    recorded = [json.loads(line) for line in (tool.recorder.directory / "tool-results.jsonl").read_text().splitlines()]
    assert recorded == [first, second]
    assert json.loads((tool.recorder.directory / "output.json").read_text()) == second
    assert json.loads((tool.recorder.directory / "input.json").read_text())["arguments"]["purpose"] == "核实适用条件"


def test_storage_failure_propagates_instead_of_fake_read_error(reader_factory, monkeypatch):
    tool = reader_factory()
    original = tool.recorder.append
    def fail(name, value):
        if name == "tool-results.jsonl":
            raise OSError("disk full")
        original(name, value)
    monkeypatch.setattr(tool.recorder, "append", fail)
    with pytest.raises(OSError, match="disk full"):
        read(tool)
    assert not (tool.recorder.directory / "output.json").exists()
