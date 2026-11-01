"""Reading uses the retrieval isolation fixture, but never constructs an Agent."""

from knowledge_agent.reading.session import create_read_tool
from tests.support.retrieval import ROOT
import json
import pytest


@pytest.fixture
def reader_factory(retrieval_settings):
    def create(fixture="F1_single_rule", *, settings=None, corpus=None, prepared=None):
        return create_read_tool(settings or retrieval_settings,
                                corpus or ROOT / "data/fixtures" / fixture / "manifest.json",
                                prepared or ROOT / "data/prepared" / f"{fixture}.json")
    return create


@pytest.fixture
def business_reader(reader_factory, archive_run):
    def create(case_id, fixture="F1_single_rule", **kwargs):
        tool = reader_factory(fixture, **kwargs)
        archive_run("reading", case_id, tool.recorder.directory)
        return tool
    return create


@pytest.fixture
def long_reader(preparation_settings, reader_factory, tmp_path):
    """Real tokenizer preparation of temporary oversized sections, never fabricated blocks."""
    corpus = tmp_path / "long-source"
    corpus.mkdir()
    body = "# 期限章节\n\n" + "国内差旅报销应记录行程，申请信息须与原始凭证对应。\n\n" * 90
    body += "# 状态章节\n\n" + "已提交仅表示进入处理队列，不能据此认定完成付款。\n\n" * 30
    (corpus / "D20.md").write_text(body, encoding="utf-8")
    (corpus / "manifest.json").write_text(json.dumps({"schema_version": 1, "documents": [{
        "doc_id": "D20", "title": "合成大文档", "version_date": "2026-01-01", "source_path": "D20.md"}]}))
    settings = preparation_settings.model_copy(update={"chunk_target_tokens": 64, "chunk_max_tokens": 96,
                                                       "chunk_overlap_tokens": 8, "max_tool_chars": 160})
    return reader_factory(settings=settings, corpus=corpus / "manifest.json", prepared=tmp_path / "long-prepared.json")
