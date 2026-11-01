"""Oversized reads, bounded locator cursors and exact source boundaries."""

import json
import pytest

from knowledge_agent.errors import CorpusError
from knowledge_agent.reading.tool import ReadTool

pytestmark = pytest.mark.boundary


def read(tool, *, call_id="boundary-read", **args):
    return tool.execute({"doc_id": "D20", "purpose": "验证读取边界", **args}, call_id=call_id)


@pytest.mark.parametrize("selector", [None, "D20-S0001"])
def test_oversized_selection_lists_all_local_blocks_then_reads_each(long_reader, selector):
    tool = long_reader
    args = {"section_id": selector} if selector else {}
    expected = [c.chunk_id for c in tool.snapshot.chunks if not selector or c.section_id == selector]
    assert len(expected) > 20
    result = read(tool, **args)
    locators = []
    while True:
        assert result["status"] == "error" and result["errors"][0]["code"] == "CONTENT_TOO_LARGE"
        assert result["data"]["segments"] == [] and result["data"]["hits"] == []
        assert result["execution"]["return_limited"] and tool.evidence.snapshot() == []
        page = result["data"]["locators"]
        assert 1 <= len(page) <= 20
        assert all("text" not in loc and "evidence_id" not in loc for loc in page)
        locators.extend(page)
        cursor = result["execution"]["next_cursor"]
        assert result["execution"]["has_more"] == (cursor is not None)
        if cursor is None:
            break
        result = read(tool, **args, cursor=cursor, purpose="继续取得定位项")
    assert [loc["chunk_id"] for loc in locators] == expected
    for index, loc in enumerate(locators):
        assert set(loc["read_args"]) == {"doc_id", "chunk_id"}
        result = read(tool, **loc["read_args"], call_id=f"local-{index}")
        assert result["status"] == "ok" and not result["data"]["locators"]
        segment = result["data"]["segments"][0]
        assert segment["source_span"] == loc["source_span"]
        assert len(segment["text"]) + len(segment["section_heading"] or "") <= 160


@pytest.mark.parametrize("change", [
    {"doc_id": "OTHER"}, {"section_id": "D20-S0001"}, {"chunk_id": "D20-C0001"},
])
def test_locator_cursor_cannot_change_selector(long_reader, change):
    cursor = read(long_reader)["execution"]["next_cursor"]
    result = read(long_reader, cursor=cursor, **change)
    assert result["errors"][0]["code"] == "INVALID_CURSOR"
    assert long_reader.evidence.snapshot() == []


def test_cursor_binds_budget_and_has_bounded_lifetime(long_reader):
    tool = long_reader
    tool.settings = tool.settings.model_copy(update={"read_cursor_capacity": 1})
    cursor = read(tool)["execution"]["next_cursor"]
    read(tool)
    assert read(tool, cursor=cursor)["errors"][0]["code"] == "INVALID_CURSOR"
    cursor = read(tool)["execution"]["next_cursor"]
    tool.settings = tool.settings.model_copy(update={"max_tool_chars": 161})
    assert read(tool, cursor=cursor)["errors"][0]["code"] == "INVALID_CURSOR"


def test_replaying_cursor_is_stable_and_returned_locators_cannot_mutate_state(long_reader):
    first = read(long_reader)
    cursor = first["execution"]["next_cursor"]
    first["data"]["locators"][0]["read_args"]["doc_id"] = "tampered"
    second = read(long_reader, cursor=cursor)
    expected = json.loads(json.dumps(second["data"]["locators"]))
    second["data"]["locators"][0]["read_args"]["doc_id"] = "tampered"
    assert read(long_reader, cursor=cursor)["data"]["locators"] == expected


def test_cursors_cannot_cross_tools_instances_or_snapshots(long_reader, reader_factory, tool_factory):
    search = tool_factory()
    search_cursor = search.execute({"query": "报销", "purpose": "取得搜索页", "limit": 1}, call_id="search")["execution"]["next_cursor"]
    assert read(long_reader, cursor=search_cursor)["errors"][0]["code"] == "INVALID_CURSOR"
    read_cursor = read(long_reader)["execution"]["next_cursor"]
    result = search.execute({"query": "报销", "purpose": "验证跨工具拒绝", "limit": 1, "cursor": read_cursor}, call_id="invalid")
    assert result["errors"][0]["code"] == "INVALID_CURSOR"
    other_instance = ReadTool(long_reader.snapshot, long_reader.settings, long_reader.evidence, long_reader.recorder)
    assert read(other_instance, cursor=read_cursor)["errors"][0]["code"] == "INVALID_CURSOR"
    assert read(reader_factory(), doc_id="D01", cursor=read_cursor)["errors"][0]["code"] == "INVALID_CURSOR"


@pytest.mark.parametrize("cursor", ["forged", ""])
def test_short_document_rejects_invalid_cursor(reader_factory, cursor):
    assert read(reader_factory(), doc_id="D01", cursor=cursor)["errors"][0]["code"] == "INVALID_CURSOR"


@pytest.mark.parametrize("strategy", ["document", "section"])
def test_exact_character_budget_succeeds_one_less_returns_only_locators(reader_factory, retrieval_settings, strategy):
    tool = reader_factory("R1_section_context")
    args = {"doc_id": "D10", **({"section_id": "D10-S0002"} if strategy == "section" else {})}
    segments = read(tool, **args)["data"]["segments"]
    size = sum(len(s["text"]) + len(s["section_heading"] or "") for s in segments)
    for budget, status in [(size, "ok"), (size - 1, "error")]:
        reader = reader_factory("R1_section_context", settings=retrieval_settings.model_copy(update={"max_tool_chars": budget}))
        result = read(reader, **args)
        assert result["status"] == status
        if status == "error":
            assert result["errors"][0]["code"] == "CONTENT_TOO_LARGE"
            assert result["data"]["segments"] == [] and reader.evidence.snapshot() == []


def test_too_small_block_budget_cannot_create_recursive_locators(reader_factory, retrieval_settings):
    with pytest.raises(CorpusError, match="预算"):
        reader_factory(settings=retrieval_settings.model_copy(update={"max_tool_chars": 1}))
    tool = reader_factory()
    tool.settings = tool.settings.model_copy(update={"max_tool_chars": 1})
    result = read(tool, doc_id="D01", chunk_id="D01-C0001")
    assert result["errors"][0]["code"] == "RETURN_BUDGET_TOO_SMALL"
    assert result["data"] == {"hits": [], "segments": [], "locators": []}
    assert result["execution"]["next_cursor"] is None and tool.evidence.snapshot() == []


def test_root_document_preserves_unicode_crlf_and_whitespace(reader_factory, preparation_settings, tmp_path):
    corpus = tmp_path / "root-source"
    corpus.mkdir()
    body = "  国内差旅😀\r\n\r\n申请须在行程结束后 30 天内提交。\r\n"
    (corpus / "doc.md").write_bytes(body.encode("utf-8"))
    (corpus / "manifest.json").write_text(json.dumps({"schema_version": 1, "documents": [{
        "doc_id": "ROOTDOC", "title": "元数据标题不冒充原文", "version_date": "2026-01-01", "source_path": "doc.md"}]}))
    tool = reader_factory(settings=preparation_settings, corpus=corpus / "manifest.json", prepared=tmp_path / "root-prepared.json")
    for args in [{}, {"section_id": "ROOTDOC-ROOT"}, {"chunk_id": "ROOTDOC-C0001"}]:
        result = read(tool, doc_id="ROOTDOC", **args)
        segment = result["data"]["segments"][0]
        assert segment["text"] == body and segment["source_span"] == {"start": 0, "end": len(body)}
        assert segment["section_id"] == "ROOTDOC-ROOT"
        assert segment["section_heading"] is None and segment["heading_span"] is None
