"""Standalone read-tool composition, reusing the authoritative retrieval snapshot."""

from pathlib import Path
from uuid import uuid4

from knowledge_agent.config import Settings
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.reading.tool import ReadTool
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.trace import RunRecorder


def create_read_tool(settings: Settings, corpus: Path, prepared: Path, *, output_dir: Path | None = None) -> ReadTool:
    snapshot = RetrievalSnapshot.load(corpus, prepared, settings)
    run_id = uuid4().hex
    recorder = RunRecorder((output_dir or settings.output_dir) / run_id, run_id)
    recorder.write("run.json", {"run_id": run_id, "stage": "standalone_read_tool", "origin": "direct_tool",
                               "model_calls": 0, "config": settings.model_dump(mode="json", include={
                                   "max_tool_chars", "chunk_target_tokens", "chunk_max_tokens",
                                   "chunk_overlap_tokens", "read_cursor_capacity"})})
    recorder.write("corpus.json", {"corpus_hash": snapshot.corpus_hash, "documents": snapshot.snapshot(),
                                  "prepared": snapshot.prepared.model_dump(mode="json")})
    return ReadTool(snapshot, settings, EvidenceStore(run_id, snapshot.corpus_hash), recorder)
