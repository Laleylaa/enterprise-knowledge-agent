"""RRF/error/cursor contracts with declared controlled rankings, no model scores."""

import asyncio
from itertools import product
from uuid import uuid4

import pytest

from knowledge_agent.config import Settings
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.retrieval.hybrid import HybridIndex
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.retrieval.tool import SearchTool
from knowledge_agent.trace import RunRecorder
from tests.support.retrieval import ROOT

pytestmark = pytest.mark.contract


class RankedBranch:
    def __init__(self, name, snapshot, order, status="ok"):
        self.strategy, self.snapshot, self.order, self.status = name, snapshot, order, status
        self.manifest = {"controlled_branch": name}
        self.calls = 0

    def rank(self, query, doc_ids):
        self.calls += 1
        if self.status == "fail":
            raise OSError("PRIVATE_FAILURE")
        return [] if self.status == "empty" else [c for c in self.order if doc_ids is None or c.doc_id in doc_ids]

    async def arank(self, query, doc_ids, **kwargs):
        return self.rank(query, doc_ids)


@pytest.fixture
def hybrid(retrieval_settings, tmp_path):
    snapshot = RetrievalSnapshot.load(ROOT / "data/fixtures/F2_conflicting_rules/manifest.json",
                                      ROOT / "data/prepared/F2_conflicting_rules.json", retrieval_settings)
    chunks = snapshot.chunks
    bm25 = RankedBranch("bm25", snapshot, [chunks[0], chunks[1], chunks[2]])
    vector = RankedBranch("vector", snapshot, [chunks[2], chunks[1], chunks[3]])
    index = HybridIndex(snapshot, retrieval_settings, bm25=bm25, vector=vector)
    identity = uuid4().hex
    return SearchTool(index, retrieval_settings, EvidenceStore(identity, snapshot.corpus_hash),
                      RunRecorder(tmp_path / "runs" / identity, identity))


def call(tool, **kwargs):
    return tool.execute({"query": "报销期限", "purpose": "受控 RRF 契约", "limit": 10, **kwargs}, call_id=uuid4().hex)


@pytest.mark.parametrize("left,right", [("ok", "fail"), ("fail", "fail")])
def test_branch_matrix_reports_empty_partial_and_total_failure(hybrid, left, right):
    hybrid.index.backends["bm25"].status = left
    hybrid.index.backends["vector"].status = right
    result = call(hybrid)
    expected = "error" if left == right == "fail" else "partial" if "fail" in (left, right) else "empty" if left == right == "empty" else "ok"
    assert result["status"] == expected
    assert result["execution"]["requested_mode"] == result["execution"]["strategy"] == "hybrid"
    assert result["execution"]["effective_branches"] == [n for n, s in (("bm25", left), ("vector", right)) if s != "fail"]
    assert [e["target"]["id"] for e in result["errors"]] == [n for n, s in (("bm25", left), ("vector", right)) if s == "fail"]
    assert "PRIVATE_FAILURE" not in str(result)
