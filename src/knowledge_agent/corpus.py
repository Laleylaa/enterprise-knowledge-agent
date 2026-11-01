"""Immutable, tiny fixture store for integration; no ranked retrieval yet."""

import hashlib
import json
from pathlib import Path
from typing import Protocol

from knowledge_agent.document_loader import load_documents
from knowledge_agent.errors import CorpusError
from knowledge_agent.schemas import Document


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class KnowledgeSource(Protocol):
    """Small read-only boundary, to be extended by the retrieval phase."""

    corpus_hash: str
    strategy: str

    def candidates(self) -> list[Document]: ...
    def get(self, doc_id: str) -> Document | None: ...
    def snapshot(self) -> list[dict]: ...


class FixtureCorpus:
    strategy = "smoke_fixture"

    def __init__(self, documents: list[Document]):
        if not documents or len({d.doc_id for d in documents}) != len(documents):
            raise CorpusError("资料不能为空，文档 ID 不能重复。")
        self._documents = {d.doc_id: d.model_copy(deep=True) for d in documents}
        serialized = [d.model_dump(mode="json") for d in self._documents.values()]
        self.corpus_hash = fingerprint(json.dumps(serialized, ensure_ascii=False, sort_keys=True))

    @classmethod
    def load(cls, path: Path, max_chars: int) -> "FixtureCorpus":
        documents = load_documents(path)
        if sum(len(d.body) for d in documents) > max_chars:
            raise CorpusError("冒烟资料超过单次返回预算；此阶段不支持分页，请使用小型资料集。")
        return cls(documents)

    def candidates(self) -> list[Document]:
        """Return the entire small fixture; intentionally NOT a search algorithm."""
        return [d.model_copy(deep=True) for d in self._documents.values()]

    def get(self, doc_id: str) -> Document | None:
        document = self._documents.get(doc_id)
        return document.model_copy(deep=True) if document else None

    def snapshot(self) -> list[dict]:
        return [d.model_dump(mode="json") for d in self._documents.values()]
