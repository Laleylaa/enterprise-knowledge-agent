"""Exact normalized BGE retrieval over the same immutable blocks as BM25."""

import hashlib
import json
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from zipfile import BadZipFile

import numpy as np

from knowledge_agent.config import Settings
from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.embedding_worker import EmbeddingWorker
from knowledge_agent.retrieval.failures import RetrievalFailure
from knowledge_agent.retrieval.model_assets import DIMENSION, MAX_TOKENS, QUERY_INSTRUCTION, validate_model
from knowledge_agent.retrieval.models import Chunk, digest
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.retrieval.tokenizer import BgeTokenizer


def library_versions() -> dict:
    try:
        return {name: version(name) for name in (
            "sentence-transformers", "transformers", "torch", "tokenizers", "numpy", "safetensors")}
    except PackageNotFoundError as exc:
        raise CorpusError("缺少向量推理依赖，请安装 requirements.txt。") from exc


def checked_vectors(values: np.ndarray, count: int) -> np.ndarray:
    if (values.shape != (count, DIMENSION) or values.dtype != np.float32 or
            not np.isfinite(values).all() or
            not np.allclose(np.linalg.norm(values, axis=1), 1.0, atol=1e-4)):
        raise RetrievalFailure("EMBEDDING_INVALID_RESULT", "Embedding 向量维度、数值或归一化校验失败。")
    return np.ascontiguousarray(values)


def matrix_hash(values: np.ndarray) -> str:
    return hashlib.sha256(values.tobytes(order="C")).hexdigest()


class VectorIndex:
    strategy = "vector"

    def __init__(self, snapshot, settings, worker, tokenizer, vectors, manifest, cache_status):
        self.snapshot, self.settings = snapshot, settings
        self.worker, self.tokenizer = worker, tokenizer
        self.vectors = checked_vectors(vectors, len(snapshot.chunks))
        self.vectors.setflags(write=False)
        self.manifest = manifest
        self.index_hash = digest(manifest)
        self.cache_status = cache_status

    @classmethod
    def load(cls, snapshot: RetrievalSnapshot, settings: Settings, *, worker=None) -> "VectorIndex":
        assets = validate_model(settings.embedding_model_path)
        tokenizer = BgeTokenizer(settings.embedding_model_path / "tokenizer.json")
        manifest = {
            "schema_version": 1, "corpus_hash": snapshot.corpus_hash,
            "chunks_hash": snapshot.prepared.chunks_hash,
            "chunk_ids": [c.chunk_id for c in snapshot.chunks],
            "encoder": {**assets, "libraries": library_versions(), "device": "cpu", "dtype": "float32",
                        "dimension": DIMENSION, "max_tokens": MAX_TOKENS, "normalize": True,
                        "query_instruction": QUERY_INSTRUCTION, "document_instruction": "",
                        "batch_size": settings.embedding_batch_size, "threads": settings.embedding_threads,
                        "algorithm": "bge-exact-cosine-v1"},
        }
        directory = settings.retrieval_cache_dir / "vector"
        path = directory / f"{digest(manifest)}.npz"
        vectors, status = None, "created"
        if path.exists():
            try:
                with np.load(path, allow_pickle=False) as cached:
                    record = json.loads(str(cached["manifest"].item()))
                    values = checked_vectors(cached["vectors"], len(snapshot.chunks))
                    if record != {"identity": manifest, "vectors_sha256": matrix_hash(values)}:
                        raise ValueError("Stale identity or corrupted vectors")
                    vectors, status = values, "hit"
            except (OSError, ValueError, KeyError, EOFError, BadZipFile, RetrievalFailure):
                # Current assets are already verified; rebuild locally, never use bad data.
                status = "rebuilt_invalid"
        worker = worker if worker is not None else EmbeddingWorker(settings)
        try:
            worker.start()
            if vectors is None:
                texts = [c.index_text for c in snapshot.chunks]
                if any(tokenizer.count(text) > MAX_TOKENS for text in texts):
                    raise CorpusError("原文索引输入超过 BGE token 上限，请重新 prepare。")
                vectors = checked_vectors(worker.encode(texts, timeout=settings.embedding_prepare_timeout), len(texts))
                directory.mkdir(parents=True, exist_ok=True)
                fd, name = tempfile.mkstemp(prefix=".vector-", suffix=".npz", dir=directory)
                temporary = Path(name)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        np.savez(stream, vectors=vectors, manifest=json.dumps({
                            "identity": manifest, "vectors_sha256": matrix_hash(vectors)}, ensure_ascii=False, sort_keys=True))
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
            return cls(snapshot, settings, worker, tokenizer, vectors, manifest, status)
        except BaseException:
            worker.close()
            raise

    def _query(self, query: str) -> str:
        # No hidden tokenizer truncation, and no double instruction for an already prefixed query.
        text = query if query.startswith(QUERY_INSTRUCTION) else QUERY_INSTRUCTION + query
        if len(text) > self.settings.max_input_chars or self.tokenizer.count(text) > MAX_TOKENS:
            raise RetrievalFailure("QUERY_TOO_LONG", "查询加检索指令超过 BGE 输入上限，请缩短查询；未截断。")
        return text

    def _rank(self, query_vector: np.ndarray, doc_ids: tuple[str, ...] | None) -> list[Chunk]:
        query_vector = checked_vectors(query_vector, 1)[0]
        scores = self.vectors @ query_vector
        candidates = [(float(scores[i]), chunk) for i, chunk in enumerate(self.snapshot.chunks)
                      if doc_ids is None or chunk.doc_id in doc_ids]
        candidates.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
        return [chunk for _, chunk in candidates]

    def rank(self, query: str, doc_ids: tuple[str, ...] | None) -> list[Chunk]:
        return self._rank(self.worker.encode([self._query(query)]), doc_ids)

    async def arank(self, query: str, doc_ids: tuple[str, ...] | None, *, timeout=None) -> list[Chunk]:
        return self._rank(await self.worker.aencode([self._query(query)], timeout=timeout), doc_ids)

    def lookup(self, doc_ids: tuple[str, ...]) -> list[Chunk]:
        return [chunk for doc_id in doc_ids for chunk in self.snapshot.chunks if chunk.doc_id == doc_id]

    def close(self):
        self.worker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
