"""Public selectors, exact sources, shared search IDs, evidence and failures."""

import json
import pytest

from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.reading.tool import ReadRequest, ReadTool
from knowledge_agent.schemas import Answer

pytestmark = pytest.mark.contract


def read(tool, **args):
    return tool.execute({"doc_id": "D01", "purpose": "核对读取契约", **args}, call_id="contract-read")


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
