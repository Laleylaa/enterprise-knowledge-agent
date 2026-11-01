"""Search arguments, identity, source spans, pagination and failure contracts."""

import json

import pytest

from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.tool import SearchRequest

pytestmark = pytest.mark.contract


def call(tool, *, call_id="test-call", **overrides):
    return tool.execute({"query": "差旅报销期限", "purpose": "核对工具契约", **overrides}, call_id=call_id)


@pytest.mark.parametrize("overrides", [
    {"query": " "}, {"purpose": "\t"}, {"doc_ids": []}, {"doc_ids": [""]},
    {"limit": 0}, {"limit": 11}, {"limit": True}, {"limit": "2"}, {"unknown": "field"},
])
def test_invalid_arguments_do_not_run_retrieval(tool_factory, monkeypatch, overrides):
    tool = tool_factory()
    monkeypatch.setattr(tool.index, "rank", lambda *a: pytest.fail("Invalid input must not execute retrieval"))
    result = call(tool, **overrides)
    assert result["status"] == "error" and result["errors"][0]["code"] == "INVALID_ARGUMENT"
    assert result["data"]["hits"] == [] and tool.evidence.snapshot() == []


def test_schema_describes_only_public_search_arguments():
    schema = SearchRequest.model_json_schema()
    assert set(schema["properties"]) == {"query", "purpose", "doc_ids", "limit", "cursor"}
    assert set(schema["required"]) == {"query", "purpose"}
    assert schema["additionalProperties"] is False


def test_hits_and_evidence_match_original_unicode_positions(tool_factory):
    tool = tool_factory()
    result = call(tool)
    evidence = {e.evidence_id: e for e in tool.evidence.snapshot()}
    for hit in result["data"]["hits"]:
        document = tool.index.snapshot.get(hit["doc_id"])
        span = hit["source_span"]
        assert hit["text"] == document.body[span["start"]:span["end"]]
        heading = hit["heading_span"]
        assert hit["section_heading"] == document.body[heading["start"]:heading["end"]]
        item = evidence[hit["evidence_id"]]
        assert item.tool_call_id == "test-call" and item.corpus_hash == result["corpus_hash"]
        assert item.text == hit["text"] and item.content_hash == hit["content_hash"]
        assert not item.delivered_to_model
        assert all(s.text == document.body[s.start:s.end] for s in item.source_spans)


def test_exact_id_lookup_preserves_order_and_deduplicates_ids(tool_factory, monkeypatch):
    tool = tool_factory("F2_conflicting_rules")
    monkeypatch.setattr(tool.index, "rank", lambda *a: pytest.fail("ID lookup cannot depend on ranking"))
    result = call(tool, query="", doc_ids=["D02", "D02", "D01"], limit=10)
    assert [h["doc_id"] for h in result["data"]["hits"]] == ["D02", "D02", "D01", "D01"]
    assert result["execution"]["strategy"] == "id_lookup"
    assert result["execution"]["effective_branches"] == []


@pytest.mark.parametrize("query,ids,status", [
    ("差旅", ["MISSING"], "error"),
    ("差旅", ["D01", "MISSING"], "partial"),
    ("量子纠缠", ["D01", "MISSING"], "partial"),
    ("量子纠缠", ["D01"], "empty"),
])
def test_partial_and_empty_are_distinct(tool_factory, query, ids, status):
    result = call(tool_factory(), query=query, doc_ids=ids)
    assert result["status"] == status
    assert all(h["doc_id"] == "D01" for h in result["data"]["hits"])
    assert [e["target"]["id"] for e in result["errors"]] == (["MISSING"] if "MISSING" in ids else [])


def test_pages_keep_original_ranking_errors_and_exact_consumption(tool_factory, monkeypatch):
    tool = tool_factory()
    args = {"doc_ids": ["D01", "MISSING"], "limit": 1}
    expected = [c.chunk_id for c in tool.index.rank("差旅报销期限", ("D01",))]
    result = call(tool, **args)
    seen = []
    monkeypatch.setattr(tool.index, "rank", lambda *a: pytest.fail("Pagination must not rerank"))
    while True:
        assert result["status"] == "partial"
        assert result["errors"][0]["target"]["id"] == "MISSING"
        seen.extend(h["chunk_id"] for h in result["data"]["hits"])
        cursor = result["execution"]["next_cursor"]
        assert result["execution"]["has_more"] == (cursor is not None)
        if cursor is None:
            break
        result = call(tool, **args, cursor=cursor, call_id=f"page-{len(seen)}", purpose="翻页目的可以变化")
    assert seen == expected and len(seen) == len(set(seen))


@pytest.mark.parametrize("changed", [{"query": "申请状态"}, {"doc_ids": ["D01"]}, {"limit": 2}])
def test_cursor_binds_query_filter_and_limit(tool_factory, changed):
    tool = tool_factory()
    first = call(tool, limit=1)
    result = call(tool, **{"limit": 1, "cursor": first["execution"]["next_cursor"], **changed})
    assert result["status"] == "error" and result["errors"][0]["code"] == "INVALID_CURSOR"


def test_unknown_cross_snapshot_and_evicted_cursors_are_rejected(tool_factory, retrieval_settings):
    tool = tool_factory(settings=retrieval_settings.model_copy(update={"search_cursor_capacity": 1}))
    cursor = call(tool, limit=1)["execution"]["next_cursor"]
    other = tool_factory("F2_conflicting_rules")
    assert call(other, limit=1, cursor=cursor)["errors"][0]["code"] == "INVALID_CURSOR"
    call(tool, limit=1)  # The bounded cursor store evicts the old result set.
    assert call(tool, limit=1, cursor=cursor)["errors"][0]["code"] == "INVALID_CURSOR"
    assert call(tool, cursor="forged")["errors"][0]["code"] == "INVALID_CURSOR"


def test_character_budget_pages_whole_blocks_without_skipping(tool_factory, retrieval_settings):
    tool = tool_factory(settings=retrieval_settings.model_copy(update={"max_tool_chars": 120}))
    args = {"query": "", "doc_ids": ["D01"], "limit": 10}
    result = call(tool, **args)
    assert result["execution"]["return_limited"]
    ids = []
    while True:
        hits = result["data"]["hits"]
        assert sum(len(h["text"]) + len(h["section_heading"] or "") for h in hits) <= 120
        ids.extend(h["chunk_id"] for h in hits)
        cursor = result["execution"]["next_cursor"]
        if cursor is None:
            break
        result = call(tool, **args, cursor=cursor)
    assert ids == [c.chunk_id for c in tool.index.snapshot.chunks]


def test_unusable_startup_budget_and_defensive_first_block_error(tool_factory, retrieval_settings):
    with pytest.raises(CorpusError, match="预算"):
        tool_factory(settings=retrieval_settings.model_copy(update={"max_tool_chars": 1}))
    tool = tool_factory()
    tool.settings = tool.settings.model_copy(update={"max_tool_chars": 1})
    response = call(tool)
    assert response["errors"][0]["code"] == "RETURN_BUDGET_TOO_SMALL"
    assert response["data"]["hits"] == [] and response["execution"]["next_cursor"] is None
    assert tool.evidence.snapshot() == []


def test_backend_failure_is_not_empty_or_fallback(tool_factory, monkeypatch):
    tool = tool_factory()
    def fail(*args):
        raise OSError("PRIVATE_BACKEND_DETAILS")
    monkeypatch.setattr(tool.index, "rank", fail)
    response = call(tool)
    assert response["status"] == "error" and response["errors"][0]["code"] == "SEARCH_FAILED"
    assert response["errors"][0]["retryable"] and response["execution"]["effective_branches"] == []
    assert response["data"]["hits"] == [] and tool.evidence.snapshot() == []
    assert "PRIVATE_BACKEND_DETAILS" not in "".join(p.read_text() for p in tool.recorder.directory.iterdir())


def test_purpose_does_not_change_ranking_and_all_records_are_actual(tool_factory):
    tool = tool_factory()
    first = call(tool, purpose="查期限", call_id="first")
    second = call(tool, purpose="查找可核对的原文", call_id="second")
    assert [h["chunk_id"] for h in first["data"]["hits"]] == [h["chunk_id"] for h in second["data"]["hits"]]
    records = [json.loads(line) for line in (tool.recorder.directory / "tool-results.jsonl").read_text().splitlines()]
    assert records == [first, second]
