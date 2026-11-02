"""Real source observations, not scripted Agent decisions or business answers."""

import shutil
import pytest

from knowledge_agent.retrieval.bm25 import Bm25Index
from knowledge_agent.retrieval.tool import SearchTool
from tests.support.retrieval import ROOT

pytestmark = pytest.mark.contract


def read(tool, *, call_id="read-1", **args):
    return tool.execute({"doc_id": "D01", "purpose": "取得可核对的制度原文", **args}, call_id=call_id)


def test_search_chunk_can_expand_to_section_with_additional_scope(reader_factory):
    tool = reader_factory("R1_section_context")
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
    assert "仅适用于国内差旅" in text and "30 天内提交" in text
    assert "## 其他事项" not in text
    assert all(not e.delivered_to_model for e in tool.evidence.snapshot())
