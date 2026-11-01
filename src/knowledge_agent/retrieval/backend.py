"""Internal index contract; model-visible search parameters stay unchanged."""

from typing import Protocol
from dataclasses import dataclass
from time import monotonic

from knowledge_agent.retrieval.models import Chunk
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.retrieval.failures import RetrievalFailure


class RetrievalIndex(Protocol):
    strategy: str
    snapshot: RetrievalSnapshot
    index_hash: str
    manifest: dict

    def lookup(self, doc_ids: tuple[str, ...]) -> list[Chunk]: ...


@dataclass(frozen=True)
class RankResult:
    candidates: tuple[Chunk, ...] = ()
    branches: tuple[str, ...] = ()
    errors: tuple[dict, ...] = ()
    details: tuple[dict, ...] = ()


def branch_error(name: str, exc: Exception) -> dict:
    if isinstance(exc, RetrievalFailure):
        if exc.code == "EMBEDDING_STOP_FAILED":
            raise exc  # Never call an unreaped computing worker a recoverable partial result.
        code, message, retryable = exc.code, str(exc), exc.retryable
    else:
        code, message, retryable = "SEARCH_FAILED", "本次检索分支执行失败，未能取得该分支候选。", True
    return {"code": code, "message": message, "retryable": retryable,
            "target": {"kind": "branch", "id": name}}


def failed_rank(name: str, exc: Exception, started: float) -> RankResult:
    error = branch_error(name, exc)
    return RankResult(errors=(error,), details=({"branch": name, "elapsed_seconds": monotonic() - started,
                                                "error_code": error["code"], "candidate_chunk_ids": []},))


def successful_rank(name: str, candidates, started: float) -> RankResult:
    return RankResult(tuple(candidates), (name,), details=({"branch": name,
                      "elapsed_seconds": monotonic() - started,
                      "candidate_chunk_ids": [c.chunk_id for c in candidates]},))


def rank_sync(index, query, doc_ids) -> RankResult:
    started = monotonic()
    name = getattr(index, "strategy", "bm25")
    try:
        method = getattr(index, "rank_result", None)
        if method is not None:
            return method(query, doc_ids)
        return successful_rank(name, index.rank(query, doc_ids), started)
    except Exception as exc:
        return failed_rank(name, exc, started)


async def rank_async(index, query, doc_ids, *, deadline=None) -> RankResult:
    started = monotonic()
    name = getattr(index, "strategy", "bm25")
    try:
        method = getattr(index, "arank_result", None)
        if method is not None:
            return await method(query, doc_ids, deadline=deadline)
        method = getattr(index, "arank", None)
        if method is None:
            return successful_rank(name, index.rank(query, doc_ids), started)
        timeout = None
        if deadline is not None:
            # Reserve bounded terminate+kill joins before the enclosing tool/turn deadline.
            timeout = min(index.settings.embedding_timeout,
                          deadline - monotonic() - 2 * index.settings.embedding_stop_timeout - 0.02)
            if timeout <= 0:
                raise RetrievalFailure("EMBEDDING_TIMEOUT", "剩余执行时间不足以完成编码与进程回收，未启动计算。", retryable=True)
        return successful_rank(name, await method(query, doc_ids, timeout=timeout), started)
    except Exception as exc:
        return failed_rank(name, exc, started)
