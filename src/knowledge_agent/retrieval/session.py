"""Composition for a standalone tool invocation; no model, agent or conversation."""

from pathlib import Path
from uuid import uuid4

from knowledge_agent.config import Settings
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.trace import RunRecorder
from knowledge_agent.retrieval.bm25 import Bm25Index
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.retrieval.tool import SearchTool


def create_search_tool(settings: Settings, corpus: Path, prepared: Path, *, output_dir: Path | None = None) -> SearchTool:
    snapshot = RetrievalSnapshot.load(corpus, prepared, settings)
    index = Bm25Index(snapshot, settings)
    run_id = uuid4().hex
    recorder = RunRecorder((output_dir or settings.output_dir) / run_id, run_id)
    recorder.write("run.json", {"run_id": run_id, "stage": "standalone_search_tool", "origin": "direct_tool",
                               "model_calls": 0, "retrieval": "bm25",
                               "config": settings.model_dump(mode="json", include={
                                   "max_tool_chars", "chunk_target_tokens", "chunk_max_tokens", "chunk_overlap_tokens",
                                   "bm25_k1", "bm25_b", "bm25_epsilon", "search_cursor_capacity"})})
    recorder.write("corpus.json", {"corpus_hash": snapshot.corpus_hash, "documents": snapshot.snapshot(),
                                  "prepared": snapshot.prepared.model_dump(mode="json")})
    recorder.write("index-manifest.json", {"index_hash": index.index_hash, **index.manifest})
    return SearchTool(index, settings, EvidenceStore(run_id, snapshot.corpus_hash), recorder)
