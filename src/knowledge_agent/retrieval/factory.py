"""One composition point for standalone tools and Agent knowledge sources."""

from knowledge_agent.errors import CorpusError
from knowledge_agent.retrieval.backend import branch_error
from knowledge_agent.retrieval.bm25 import Bm25Index
from knowledge_agent.retrieval.failures import RetrievalFailure


def build_index(snapshot, settings, retrieval):
    if retrieval == "bm25":
        return Bm25Index(snapshot, settings)
    if retrieval not in {"vector", "hybrid"}:
        raise ValueError("Unknown retrieval mode")
    # Do not import neural dependencies or create workers on the BM25 path.
    from knowledge_agent.retrieval.embedding_worker import EmbeddingWorker
    from knowledge_agent.retrieval.vector import VectorIndex
    worker = EmbeddingWorker(settings)
    if retrieval == "vector":
        try:
            return VectorIndex.load(snapshot, settings, worker=worker)
        except BaseException:
            worker.close()
            raise
    from knowledge_agent.retrieval.hybrid import HybridIndex
    errors, backends = [], {}
    try:
        for name, create in (("bm25", lambda: Bm25Index(snapshot, settings)),
                             ("vector", lambda: VectorIndex.load(snapshot, settings, worker=worker))):
            try:
                backends[name] = create()
            except (CorpusError, RetrievalFailure, ImportError, OSError) as exc:
                if name == "vector":
                    worker.close()
                if isinstance(exc, RetrievalFailure):
                    errors.append(branch_error(name, exc))
                else:
                    errors.append(branch_error(name, RetrievalFailure(
                        "BRANCH_UNAVAILABLE", "检索分支初始化失败；请检查本地权重、依赖和缓存后重新启动。")))
        if not backends:
            raise RetrievalFailure("SEARCH_INIT_FAILED", "全部检索分支初始化失败，无法启动。")
        return HybridIndex(snapshot, settings, **backends, startup_errors=errors,
                           startup_events=worker.events if "vector" not in backends else ())
    except BaseException:
        worker.close()
        raise
