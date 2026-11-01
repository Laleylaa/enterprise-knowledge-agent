"""Prepared read-only knowledge base shared by all tools in a turn."""

from pathlib import Path
from contextlib import contextmanager
from uuid import uuid4

from knowledge_agent.config import Settings
from knowledge_agent.retrieval.factory import build_index
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.trace import RunRecorder


class IndexedCorpus:
    def __init__(self, snapshot: RetrievalSnapshot, settings: Settings):
        self.retrieval_snapshot = snapshot
        self.strategy = settings.selected_retrieval
        self.index = build_index(snapshot, settings, self.strategy)
        self.corpus_hash = snapshot.corpus_hash

    @classmethod
    def load(cls, corpus: Path, prepared: Path, settings: Settings) -> "IndexedCorpus":
        return cls(RetrievalSnapshot.load(corpus, prepared, settings), settings)

    def snapshot(self) -> list[dict]:
        return self.retrieval_snapshot.snapshot()

    def close(self):
        close = getattr(self.index, "close", None)
        if close is not None:
            close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@contextmanager
def open_indexed_source(settings):
    """CLI owns one index/worker across all turns; audit startup and final disposal."""
    identity = uuid4().hex
    recorder = RunRecorder(settings.output_dir / "retrieval" / identity, identity)
    source = None
    recorder.event("retrieval_initializing", requested_mode=settings.selected_retrieval)
    try:
        source = IndexedCorpus.load(settings.corpus_path, settings.prepared_path, settings)
        recorder.write("index-manifest.json", {"index_hash": source.index.index_hash, **source.index.manifest})
        recorder.event("retrieval_initialized", requested_mode=source.strategy,
                       errors=list(getattr(source.index, "startup_errors", ())))
        yield source
    except BaseException as exc:
        recorder.event("retrieval_scope_failed", error_type=type(exc).__name__)
        raise
    finally:
        if source is not None:
            try:
                source.close()
            except BaseException as exc:
                recorder.event("retrieval_close_failed", error_type=type(exc).__name__)
                raise
            else:
                recorder.event("retrieval_closed")
            finally:
                worker = getattr(source.index, "worker", None)
                events = list(getattr(source.index, "startup_events", ())) + (worker.events if worker else [])
                for event in events:
                    recorder.event(event["event"], **{k: v for k, v in event.items() if k != "event"})
