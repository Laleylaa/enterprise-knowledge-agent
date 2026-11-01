"""Per-run evidence identity and exact-quote validation, without semantic judgment."""

from knowledge_agent.corpus import fingerprint
from knowledge_agent.schemas import Answer, Document, Evidence


class EvidenceStore:
    def __init__(self, run_id: str, corpus_hash: str):
        self.run_id = run_id
        self.corpus_hash = corpus_hash
        self._items: dict[str, Evidence] = {}

    def add(self, document: Document, tool_call_id: str) -> Evidence:
        item = Evidence(
            evidence_id=f"{self.run_id}:E{len(self._items) + 1}",
            tool_call_id=tool_call_id,
            corpus_hash=self.corpus_hash,
            doc_id=document.doc_id,
            title=document.title,
            version_date=document.version_date,
            content_hash=fingerprint(document.body),
            start=0,
            end=len(document.body),
            text=document.body,
        )
        self._items[item.evidence_id] = item
        return item

    def mark_delivered(self, tool_call_ids: set[str]) -> None:
        for item in self._items.values():
            if item.tool_call_id in tool_call_ids:
                item.delivered_to_model = True

    def validate(self, result: Answer) -> None:
        for index, citation in enumerate(result.citations):
            item = self._items.get(citation.evidence_id)
            if item is None or not item.delivered_to_model:
                raise ValueError(f"citations.{index}.evidence_id：引用必须来自本轮已反馈给模型的证据。")
            if citation.doc_id != item.doc_id or citation.quote not in item.text:
                raise ValueError(f"citations.{index}：引用文档不匹配，或引文不是对应原文的连续片段。")

    def snapshot(self) -> list[Evidence]:
        return [item.model_copy(deep=True) for item in self._items.values()]
