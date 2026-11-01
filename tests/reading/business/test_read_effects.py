"""Real source observations, not scripted Agent decisions or business answers."""

import shutil
import pytest

from knowledge_agent.retrieval.bm25 import Bm25Index
from knowledge_agent.retrieval.tool import SearchTool
from tests.support.retrieval import ROOT

pytestmark = pytest.mark.business


def read(tool, *, call_id="read-1", **args):
    return tool.execute({"doc_id": "D01", "purpose": "取得可核对的制度原文", **args}, call_id=call_id)


def metric(tool, **values):
    tool.recorder.write("reading-evaluation.json", {"scope": "single_read_tool", "model_calls": 0, **values})


def test_full_document_retains_clause_and_conditions(business_reader):
    tool = business_reader("normal")
    result = read(tool)
    text = "".join(s["text"] for s in result["data"]["segments"])
    matches = text == tool.snapshot.get("D01").body
    metric(tool, status=result["status"], exact_full_document=matches,
           supporting_clause_present="国内差旅报销须在行程结束后 30 天内提交。" in text)
    assert matches and "国内差旅报销须在行程结束后 30 天内提交。" in text


def test_search_chunk_can_expand_to_section_with_additional_scope(business_reader):
    tool = business_reader("section_expansion", "R1_section_context")
    index = Bm25Index(tool.snapshot, tool.settings)
    tool.recorder.write("index-manifest.json", {"index_hash": index.index_hash, **index.manifest})
    search = SearchTool(index, tool.settings, tool.evidence, tool.recorder)
    result = search.execute({"query": "草稿保存时间", "limit": 1,
                             "purpose": "直接调用搜索提供真实块定位"}, call_id="search-1")
    assert len(result["data"]["hits"]) == 1
    hit = next(h for h in result["data"]["hits"] if "30 天内提交" in h["text"])
    assert "仅适用于国内差旅" not in hit["text"]
    block = read(tool, doc_id=hit["doc_id"], chunk_id=hit["chunk_id"], call_id="read-block")
    assert block["data"]["segments"][0]["text"] == hit["text"]
    section = read(tool, doc_id=hit["doc_id"], section_id=hit["section_id"], call_id="read-section")
    text = "".join(s["text"] for s in section["data"]["segments"])
    metric(tool, trigger="test_selected_search_hit_not_model_decision", search_query="草稿保存时间", search_limit=1,
           first_observation_contains_scope=False, chunk_id=hit["chunk_id"],
           section_id=hit["section_id"], chunk_contains_scope=False,
           section_contains_scope="仅适用于国内差旅" in text,
           section_contains_deadline="30 天内提交" in text, section_chars=len(text))
    assert "仅适用于国内差旅" in text and "30 天内提交" in text
    assert "## 其他事项" not in text
    assert all(not e.delivered_to_model for e in tool.evidence.snapshot())


def test_conflicting_documents_are_preserved_without_adjudication(business_reader):
    tool = business_reader("conflicting_sources", "F2_conflicting_rules")
    texts = {}
    for doc_id in ["D01", "D02"]:
        result = read(tool, doc_id=doc_id, call_id=f"read-{doc_id}")
        texts[doc_id] = "".join(s["text"] for s in result["data"]["segments"])
        assert result["status"] == "ok" and "answer" not in result
    metric(tool, returned_documents=list(texts), first_rule_present="30 天" in texts["D01"],
           second_rule_present="15 天" in texts["D02"], adjudication=False)
    assert "30 天" in texts["D01"] and "15 天" in texts["D02"]


def test_missing_document_is_a_locator_error_not_no_policy_claim(business_reader):
    tool = business_reader("missing_source")
    result = read(tool, doc_id="D99")
    metric(tool, status=result["status"], error_codes=[e["code"] for e in result["errors"]], evidence_count=len(tool.evidence.snapshot()))
    assert result["status"] == "error" and result["errors"][0]["code"] == "NOT_FOUND"
    assert result["errors"][0]["target"] == {"kind": "doc", "id": "D99"}
    assert tool.evidence.snapshot() == []


def test_read_failure_reports_error_without_retry_or_fabricated_evidence(business_reader, monkeypatch):
    tool = business_reader("tool_failure")
    attempts = []
    def unavailable(*args):
        attempts.append(args)
        raise OSError("PRIVATE_SOURCE_DETAILS")
    monkeypatch.setattr(tool.snapshot, "get", unavailable)
    tool.recorder.write("fault-injection.json", {"scope": "test_only", "target": "RetrievalSnapshot.get",
                                                "call_number": 1, "error": "OSError"})
    result = read(tool)
    metric(tool, status=result["status"], error_codes=[e["code"] for e in result["errors"]],
           backend_attempts=len(attempts), evidence_count=len(tool.evidence.snapshot()))
    assert result["errors"][0]["code"] == "READ_FAILED" and result["errors"][0]["retryable"]
    assert result["status"] == "error" and tool.evidence.snapshot() == [] and len(attempts) == 1
    assert "PRIVATE_SOURCE_DETAILS" not in "".join(p.read_text() for p in tool.recorder.directory.iterdir())


def test_oversized_section_offers_readable_local_evidence(business_reader, retrieval_settings):
    tool = business_reader("oversized_section", "R1_section_context",
                           settings=retrieval_settings.model_copy(update={"max_tool_chars": 340}))
    first = read(tool, doc_id="D10", section_id="D10-S0002", call_id="read-section")
    assert first["errors"][0]["code"] == "CONTENT_TOO_LARGE" and tool.evidence.snapshot() == []
    text = []
    for i, loc in enumerate(first["data"]["locators"]):
        result = read(tool, **loc["read_args"], call_id=f"read-local-{i}")
        assert result["status"] == "ok"
        text.extend(s["text"] for s in result["data"]["segments"])
    metric(tool, initial_status=first["status"], locator_count=len(first["data"]["locators"]),
           successful_chunk_reads=len(text), recovered_scope=any("仅适用于国内差旅" in t for t in text),
           trigger="test_selected_local_reads_not_model_recovery")
    assert any("仅适用于国内差旅" in t for t in text)


def test_reloaded_source_uses_new_text_while_open_snapshot_stays_consistent(
    business_reader, preparation_settings, tmp_path,
):
    corpus = tmp_path / "replacement"
    shutil.copytree(ROOT / "data/fixtures/F1_single_rule", corpus)
    prepared = tmp_path / "prepared.json"
    shutil.copyfile(ROOT / "data/prepared/F1_single_rule.json", prepared)
    old = business_reader("policy_before", settings=preparation_settings, corpus=corpus / "manifest.json", prepared=prepared)
    before = read(old)
    path = corpus / "documents/D01.md"
    path.write_text(path.read_text().replace("30 天", "20 天"))
    still_old = read(old, call_id="read-existing-snapshot")
    new = business_reader("policy_after", settings=preparation_settings, corpus=corpus / "manifest.json", prepared=prepared)
    after = read(new)
    old_text = "".join(s["text"] for s in still_old["data"]["segments"])
    new_text = "".join(s["text"] for s in after["data"]["segments"])
    metric(old, paired_run_id=new.recorder.run_id, snapshot_immutable=True, original_rule_present="30 天" in old_text)
    metric(new, paired_run_id=old.recorder.run_id, new_rule_present="20 天" in new_text, stale_rule_present="30 天" in new_text)
    assert before["corpus_hash"] == still_old["corpus_hash"] != after["corpus_hash"]
    assert "30 天" in old_text and "20 天" in new_text and "30 天" not in new_text
