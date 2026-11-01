"""Retrieval effects only: these cases do not assert Agent answers or decisions."""

import shutil
import pytest

from tests.support.retrieval import ROOT

pytestmark = pytest.mark.business


def observe(tool, query, *, call_id="search-1", **options):
    return tool.execute({"query": query, "purpose": "查找可核对的制度原文", **options}, call_id=call_id)


def metric(tool, **values):
    tool.recorder.write("retrieval-evaluation.json", {"scope": "single_search_tool", "model_calls": 0, **values})


@pytest.mark.parametrize("case_id,query", [("normal", "国内差旅报销期限多久？"), ("paraphrase", "国内出差回来最迟多久交报销？")], ids=["normal", "paraphrase"])
def test_retrieves_supporting_clause_in_first_page(business_tool, case_id, query):
    tool = business_tool(case_id)
    result = observe(tool, query)
    hits = result["data"]["hits"]
    supporting = [i for i, hit in enumerate(hits, 1) if "国内差旅报销须在行程结束后 30 天内提交。" in hit["text"]]
    metric(tool, query=query, returned=len(hits), supporting_ranks=supporting,
           support_in_top_5=bool(supporting), support_at_rank_1=1 in supporting)
    assert result["status"] == "ok" and supporting
    assert all(h["doc_id"] == "D01" for h in hits)


def test_keeps_both_conflicting_sources_without_selecting_a_rule(business_tool):
    tool = business_tool("conflicting_sources", "F2_conflicting_rules")
    result = observe(tool, "差旅报销期限多久？")
    supports = {h["doc_id"]: h["text"] for h in result["data"]["hits"] if "天内提交" in h["text"]}
    metric(tool, conflict_sources_found=sorted(supports), conflict_pair_coverage=len(supports) / 2)
    assert "30 天" in supports["D01"] and "15 天" in supports["D02"]
    assert result["status"] == "ok" and "answer" not in result


def test_out_of_corpus_query_is_empty_without_claiming_no_policy_exists(business_tool):
    tool = business_tool("out_of_corpus")
    result = observe(tool, "育儿假天数")
    metric(tool, query="育儿假天数", returned=len(result["data"]["hits"]), status=result["status"])
    assert result["status"] == "empty" and result["data"]["hits"] == [] and result["errors"] == []


def test_explicit_document_clue_filters_out_other_policy(business_tool):
    tool = business_tool("explicit_document", "F2_conflicting_rules")
    result = observe(tool, "", doc_ids=["D02"])
    metric(tool, requested_doc="D02", returned_docs=sorted({h["doc_id"] for h in result["data"]["hits"]}))
    assert result["execution"]["strategy"] == "id_lookup"
    assert all(h["doc_id"] == "D02" for h in result["data"]["hits"])
    assert any("15 天" in h["text"] for h in result["data"]["hits"])


def test_tool_failure_is_an_error_and_creates_no_evidence(business_tool, monkeypatch):
    tool = business_tool("tool_failure")
    def unavailable(*args):
        raise OSError("injected local index failure")
    monkeypatch.setattr(tool.index, "rank", unavailable)
    tool.recorder.write("fault-injection.json", {"scope": "test_only", "target": "Bm25Index.rank", "error": "OSError"})
    result = observe(tool, "国内差旅报销期限多久？")
    metric(tool, status=result["status"], error_codes=[e["code"] for e in result["errors"]],
           evidence_count=len(tool.evidence.snapshot()))
    assert result["status"] == "error" and result["errors"][0]["code"] == "SEARCH_FAILED"
    assert result["data"]["hits"] == [] and tool.evidence.snapshot() == []


def test_replaced_policy_is_searchable_after_repreparation(
    preparation_settings, business_tool, tmp_path,
):
    # Change a temporary Markdown source; no hand-written replacement index or expected response.
    corpus = tmp_path / "replacement"
    shutil.copytree(ROOT / "data/fixtures/F1_single_rule", corpus)
    path = corpus / "documents/D01.md"
    path.write_text(path.read_text().replace("30 天", "20 天"))
    tool = business_tool("policy_replacement", settings=preparation_settings,
                         corpus=corpus / "manifest.json",
                         prepared=tmp_path / "replacement-prepared.json")
    result = observe(tool, "国内差旅报销期限多久？")
    texts = [h["text"] for h in result["data"]["hits"]]
    metric(tool, replacement="30→20", new_clause_found=any("20 天" in text for text in texts),
           stale_clause_found=any("30 天" in text for text in texts))
    assert any("20 天" in text for text in texts) and not any("30 天" in text for text in texts)
