"""Composition for a standalone tool invocation; no model, agent or conversation."""

from pathlib import Path
from uuid import uuid4

from knowledge_agent.config import Settings
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.trace import RunRecorder
from knowledge_agent.retrieval.factory import build_index
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.retrieval.tool import SearchTool


def create_search_tool(settings: Settings, corpus: Path, prepared: Path, *, output_dir: Path | None = None,
                       retrieval: str | None = None) -> SearchTool:
    retrieval = retrieval or settings.selected_retrieval
    if retrieval not in {"bm25", "vector", "hybrid"}:
        raise ValueError("Standalone retrieval supports bm25, vector or hybrid")
    snapshot = RetrievalSnapshot.load(corpus, prepared, settings)
    run_id = uuid4().hex
    recorder = RunRecorder((output_dir or settings.output_dir) / run_id, run_id)
    recorder.write("run.json", {"run_id": run_id, "stage": "standalone_search_tool", "origin": "direct_tool",
                               "model_calls": 0, "retrieval": retrieval,
                               "config": settings.model_dump(mode="json", include={
                                   "max_tool_chars", "chunk_target_tokens", "chunk_max_tokens", "chunk_overlap_tokens",
                                   "bm25_k1", "bm25_b", "bm25_epsilon", "search_cursor_capacity",
                                   "embedding_model_path", "embedding_timeout", "embedding_startup_timeout",
                                   "embedding_prepare_timeout", "embedding_batch_size", "embedding_threads",
                                   "embedding_stop_timeout", "rrf_k"})})
    recorder.write("corpus.json", {"corpus_hash": snapshot.corpus_hash, "documents": snapshot.snapshot(),
                                  "prepared": snapshot.prepared.model_dump(mode="json")})
    try:
        index = build_index(snapshot, settings, retrieval)
    except BaseException as exc:
        recorder.event("retrieval_initialization_failed", strategy=retrieval,
                       error_code=getattr(exc, "code", None), error_type=type(exc).__name__)
        raise
    tool = SearchTool(index, settings, EvidenceStore(run_id, snapshot.corpus_hash), recorder)
    try:
        recorder.write("index-manifest.json", {"index_hash": index.index_hash, **index.manifest})
        recorder.event("retrieval_initialized", strategy=retrieval, cache_status=getattr(index, "cache_status", None),
                       startup_errors=list(getattr(index, "startup_errors", ())))
        for event in getattr(index, "startup_events", ()):
            recorder.event(event["event"], **{k: v for k, v in event.items() if k != "event"})
        tool._record_worker_events()
        return tool
    except BaseException:
        tool.close()
        raise
