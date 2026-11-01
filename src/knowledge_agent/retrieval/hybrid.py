"""Equal-weight reciprocal rank fusion; per-query degradation is never hidden."""

from fractions import Fraction

from knowledge_agent.retrieval.backend import RankResult, rank_async, rank_sync
from knowledge_agent.retrieval.models import digest


class HybridIndex:
    strategy = "hybrid"

    def __init__(self, snapshot, settings, *, bm25=None, vector=None, startup_errors=(), startup_events=()):
        self.snapshot, self.settings = snapshot, settings
        self.backends = {name: backend for name, backend in (("bm25", bm25), ("vector", vector)) if backend is not None}
        for backend in self.backends.values():
            if (backend.snapshot.corpus_hash != snapshot.corpus_hash or
                    backend.snapshot.prepared.chunks_hash != snapshot.prepared.chunks_hash):
                raise ValueError("Hybrid branches must use the same source and chunks")
        self.startup_errors = tuple(startup_errors)
        self.startup_events = tuple(startup_events)
        self.manifest = {"algorithm": "rrf-v1", "rrf_k": settings.rrf_k, "weights": {"bm25": 1, "vector": 1},
                         "corpus_hash": snapshot.corpus_hash, "chunks_hash": snapshot.prepared.chunks_hash,
                         "branches": {name: backend.manifest for name, backend in self.backends.items()},
                         "startup_errors": list(self.startup_errors)}
        self.index_hash = digest(self.manifest)

    @property
    def worker(self):
        return getattr(self.backends.get("vector"), "worker", None)

    def _merge(self, results):
        scores, chunks, branches, errors, details = {}, {}, [], list(self.startup_errors), []
        for result in results:
            branches.extend(result.branches)
            errors.extend(result.errors)
            details.extend(result.details)
            # A duplicate within one branch contributes once; cross-document IDs stay distinct.
            unique = {c.chunk_id: c for c in result.candidates}
            for rank, chunk in enumerate(unique.values(), 1):
                chunks[chunk.chunk_id] = chunk
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, Fraction()) + Fraction(1, self.settings.rrf_k + rank)
        order = sorted(chunks, key=lambda key: (-scores[key], key))
        details.extend({"branch": error["target"]["id"], "initialization_failure": True,
                        "error_code": error["code"], "candidate_chunk_ids": []} for error in self.startup_errors)
        details.append({"algorithm": "rrf", "k": self.settings.rrf_k,
                        "scores": {key: float(scores[key]) for key in order}})
        return RankResult(tuple(chunks[key] for key in order), tuple(branches), tuple(errors), tuple(details))

    def rank_result(self, query, doc_ids):
        return self._merge([rank_sync(backend, query, doc_ids) for backend in self.backends.values()])

    async def arank_result(self, query, doc_ids, *, deadline=None):
        results = []
        for backend in self.backends.values():
            results.append(await rank_async(backend, query, doc_ids, deadline=deadline))
        return self._merge(results)

    def lookup(self, doc_ids):
        return [chunk for doc_id in doc_ids for chunk in self.snapshot.chunks if chunk.doc_id == doc_id]

    def close(self):
        for backend in self.backends.values():
            close = getattr(backend, "close", None)
            if close is not None:
                close()
