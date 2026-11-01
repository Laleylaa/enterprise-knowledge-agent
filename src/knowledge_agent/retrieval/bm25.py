"""Deterministic lexical ranking with shared preprocessing and version identity."""

import hashlib
import logging
import unicodedata
from importlib.metadata import version
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from knowledge_agent.config import Settings
from knowledge_agent.retrieval.models import Chunk, digest
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot


class Bm25Index:
    strategy = "bm25"

    def __init__(self, snapshot: RetrievalSnapshot, settings: Settings):
        self.snapshot = snapshot
        dictionary = Path(jieba.__file__).with_name("dict.txt")
        settings.retrieval_cache_dir.mkdir(parents=True, exist_ok=True)
        self._segmenter = jieba.Tokenizer(str(dictionary))
        self._segmenter.tmp_dir = str(settings.retrieval_cache_dir)
        jieba.setLogLevel(logging.WARNING)
        self.manifest = {
            "corpus_hash": snapshot.corpus_hash, "chunks_hash": snapshot.prepared.chunks_hash,
            "bm25_config": {"implementation": "rank_bm25.BM25Okapi", "version": version("rank-bm25"),
                            "k1": settings.bm25_k1, "b": settings.bm25_b, "epsilon": settings.bm25_epsilon},
            "tokenization": {"jieba_version": version("jieba"), "dictionary_sha256": hashlib.sha256(dictionary.read_bytes()).hexdigest(),
                             "normalization": "NFKC-lower-alphanumeric-v1", "hmm": False, "stopwords": []},
        }
        self.index_hash = digest(self.manifest)
        self._tokens = [self.tokenize(c.index_text) for c in snapshot.chunks]
        # BM25 cannot initialize an empty vocabulary. Empty lexical content is a valid no-hit corpus.
        self._ranker = BM25Okapi(self._tokens, k1=settings.bm25_k1, b=settings.bm25_b,
                                epsilon=settings.bm25_epsilon) if any(self._tokens) else None

    def tokenize(self, text: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", text).lower()
        return [word for word in self._segmenter.cut(normalized, HMM=False)
                if any(char.isalnum() for char in word)]

    def rank(self, query: str, doc_ids: tuple[str, ...] | None) -> list[Chunk]:
        terms = self.tokenize(query)
        if not terms or self._ranker is None:
            return []
        scores = self._ranker.get_scores(terms)
        shared = set(terms)
        candidates = [(float(scores[i]), chunk) for i, chunk in enumerate(self.snapshot.chunks)
                      if (doc_ids is None or chunk.doc_id in doc_ids) and shared.intersection(self._tokens[i])]
        # Small corpora can yield zero or negative IDF. Overlap, not score > 0, decides candidacy.
        candidates.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
        return [chunk for _, chunk in candidates]

    def lookup(self, doc_ids: tuple[str, ...]) -> list[Chunk]:
        return [chunk for doc_id in doc_ids for chunk in self.snapshot.chunks if chunk.doc_id == doc_id]
