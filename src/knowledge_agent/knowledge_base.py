"""Prepared read-only knowledge base shared by all tools in a turn."""

from pathlib import Path

from knowledge_agent.config import Settings
from knowledge_agent.retrieval.bm25 import Bm25Index
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot


class IndexedCorpus:
    strategy = "bm25"

    def __init__(self, snapshot: RetrievalSnapshot, settings: Settings):
        self.retrieval_snapshot = snapshot
        self.index = Bm25Index(snapshot, settings)
        self.corpus_hash = snapshot.corpus_hash

    @classmethod
    def load(cls, corpus: Path, prepared: Path, settings: Settings) -> "IndexedCorpus":
        return cls(RetrievalSnapshot.load(corpus, prepared, settings), settings)

    def snapshot(self) -> list[dict]:
        return self.retrieval_snapshot.snapshot()
