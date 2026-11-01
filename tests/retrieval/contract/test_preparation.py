"""Only preparation/identity guarantees needed by the standalone search tool."""

import json
import shutil

import pytest

from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.models import PreparedCorpus
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot, blocks_hash, prepare_documents
from knowledge_agent.retrieval.tokenizer import BgeTokenizer
from knowledge_agent.schemas import Answer, Document
from tests.support.retrieval import ROOT

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("body", [
    "前言😀\r\n\r\n# 国内差旅\r\n" + "差旅报销须在行程结束后30天提交。\r\n" * 40 + "\r\n## 海外\r\n海外期限15天。",
    "# " + "很长的原文章节标题" * 80 + "\n" + "不能截断原文" * 300,
    "无标题原文😀" + "abcdefghijklmnopqrstuvwxyz" * 100,
    "# 正文\n```markdown\n# 代码中的文本不构成章节\n```\n\n## 真章节\n内容。",
], ids=["paragraphs_crlf_unicode", "long_heading_and_sentence", "root_and_unknown_tokens", "fenced_heading"])
def test_real_tokenizer_chunks_cover_source_and_respect_hard_limit(preparation_settings, body):
    settings = preparation_settings.model_copy(update={"chunk_target_tokens": 96, "chunk_max_tokens": 128,
                                                       "chunk_overlap_tokens": 12})
    document = Document(doc_id="T01", title="合成原文", version_date="2026-01-01", body=body)
    prepared = prepare_documents([document], settings)
    tokenizer = BgeTokenizer(settings.tokenizer_path)
    snapshot = RetrievalSnapshot([document], prepared, settings)
    assert snapshot.get("T01").body == body
    for chunk in prepared.chunks:
        assert chunk.text == body[chunk.start:chunk.end]
        assert chunk.token_count == tokenizer.count(chunk.index_text) <= 128
        section = snapshot.sections[chunk.section_id]
        assert section.start <= chunk.start < chunk.end <= section.end
        if chunk.heading_span:
            assert body[chunk.heading_span.start:chunk.heading_span.end] == section.heading
    if body.startswith("无标题"):
        assert len(prepared.sections) == 1 and prepared.sections[0].section_id == "T01-ROOT"
        assert all(c.heading_span is None for c in prepared.chunks)
    if "代码中的文本" in body:
        assert [s.heading for s in prepared.sections] == ["正文", "真章节"]
    if body.startswith("# 很长"):
        assert any(c.context_truncated for c in prepared.chunks)
    assert prepare_documents([document], settings) == prepared


@pytest.mark.parametrize("damage", ["text", "missing_block", "heading", "index_text"])
def test_modified_prepared_spans_and_missing_coverage_are_rejected(retrieval_settings, tmp_path, damage):
    payload = json.loads((ROOT / "data/prepared/F1_single_rule.json").read_text())
    if damage == "text":
        payload["chunks"][2]["text"] = "篡改后的制度"
    elif damage == "missing_block":
        payload["chunks"].pop()
    elif damage == "heading":
        payload["sections"][0]["heading"] = "原文没有这个标题"
    else:
        payload["chunks"][0]["index_text"] = "伪造排名关键词\n" + payload["chunks"][0]["text"]
    # Even a recalculated file checksum does not make invented source text legitimate.
    prepared = PreparedCorpus.model_validate(payload)
    payload["chunks_hash"] = blocks_hash(prepared.sections, prepared.chunks)
    path = tmp_path / "prepared.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(CorpusError):
        RetrievalSnapshot.load(ROOT / "data/fixtures/F1_single_rule/manifest.json", path, retrieval_settings)


def test_source_change_refuses_stale_blocks_without_tokenizer(retrieval_settings, tmp_path):
    corpus = tmp_path / "source"
    shutil.copytree(ROOT / "data/fixtures/F1_single_rule", corpus)
    original = corpus / "documents/D01.md"
    original.write_text(original.read_text().replace("30 天", "20 天"))
    with pytest.raises(CorpusError, match="过期"):
        RetrievalSnapshot.load(corpus / "manifest.json", ROOT / "data/prepared/F1_single_rule.json", retrieval_settings)


def test_reload_rebuilds_stale_snapshot_but_existing_snapshot_is_immutable(preparation_settings, tmp_path):
    corpus = tmp_path / "source"
    shutil.copytree(ROOT / "data/fixtures/F1_single_rule", corpus)
    prepared = tmp_path / "prepared.json"
    shutil.copyfile(ROOT / "data/prepared/F1_single_rule.json", prepared)
    old = RetrievalSnapshot.load(corpus / "manifest.json", prepared, preparation_settings)
    path = corpus / "documents/D01.md"
    path.write_text(path.read_text().replace("30 天", "20 天"))
    new = RetrievalSnapshot.load(corpus / "manifest.json", prepared, preparation_settings)
    assert old.corpus_hash != new.corpus_hash
    assert "30 天" in old.get("D01").body and "20 天" in new.get("D01").body
    assert PreparedCorpus.model_validate_json(prepared.read_bytes()).corpus_hash == new.corpus_hash


def test_index_identity_changes_with_bm25_configuration(tool_factory, retrieval_settings):
    first = tool_factory()
    second = tool_factory(settings=retrieval_settings.model_copy(update={"bm25_b": 0.5}))
    assert first.index.snapshot.corpus_hash == second.index.snapshot.corpus_hash
    assert first.index.index_hash != second.index.index_hash
    assert len(first.index.manifest["tokenization"]["dictionary_sha256"]) == 64


def test_zero_or_negative_bm25_scores_still_return_matching_candidates(preparation_settings, tmp_path, tool_factory):
    corpus = tmp_path / "single"
    corpus.mkdir()
    (corpus / "doc.md").write_text("差旅报销期限30天。")
    (corpus / "manifest.json").write_text(json.dumps({"schema_version": 1, "documents": [
        {"doc_id": "T01", "title": "差旅报销", "version_date": "2026-01-01", "source_path": "doc.md"}]}))
    prepared = tmp_path / "prepared.json"
    tool = tool_factory(settings=preparation_settings, corpus=corpus / "manifest.json", prepared=prepared)
    scores = tool.index._ranker.get_scores(tool.index.tokenize("报销"))
    assert scores[0] <= 0
    result = tool.execute({"query": "报销", "purpose": "验证小库词项匹配"}, call_id="zero-score")
    assert result["status"] == "ok" and result["data"]["hits"][0]["doc_id"] == "T01"


def test_detached_heading_is_separate_evidence_and_cannot_form_a_fused_quote(
    preparation_settings, tmp_path, tool_factory,
):
    settings = preparation_settings.model_copy(update={"chunk_target_tokens": 64, "chunk_max_tokens": 96,
                                                       "chunk_overlap_tokens": 8})
    corpus = tmp_path / "long-source"
    corpus.mkdir()
    body = "# 国内差旅\n\n" + "出差申请须记录行程信息。" * 100
    (corpus / "doc.md").write_text(body)
    (corpus / "manifest.json").write_text(json.dumps({"schema_version": 1, "documents": [
        {"doc_id": "T01", "title": "差旅规定", "version_date": "2026-01-01", "source_path": "doc.md"}]}))
    tool = tool_factory(settings=settings, corpus=corpus / "manifest.json", prepared=tmp_path / "prepared.json")
    result = tool.execute({"query": "", "doc_ids": ["T01"], "purpose": "核对长块来源", "limit": 10}, call_id="long")
    hit = next(h for h in result["data"]["hits"] if h["source_span"]["start"] > h["heading_span"]["end"])
    item = next(e for e in tool.evidence.snapshot() if e.evidence_id == hit["evidence_id"])
    assert len(item.source_spans) == 2 and all(s.text == body[s.start:s.end] for s in item.source_spans)
    # Exercise only the evidence validator; no Agent or model is invoked.
    tool.evidence.mark_delivered({"long"})
    def answer(quote):
        return Answer(status="resolved", answer="受控引用校验", gaps=[], clarification=None,
                      citations=[{"evidence_id": item.evidence_id, "doc_id": "T01", "quote": quote}],
                      decision_summary="只核对来源连续性")
    tool.evidence.validate(answer(hit["section_heading"]))
    tool.evidence.validate(answer(hit["text"]))
    with pytest.raises(ValueError):
        tool.evidence.validate(answer(hit["section_heading"] + hit["text"]))
