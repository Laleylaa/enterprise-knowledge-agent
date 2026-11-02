"""Per-run evidence identity and exact-quote validation, without semantic judgment."""

from knowledge_agent.corpus import fingerprint
from knowledge_agent.schemas import Answer, AnswerPart, Citation, Document, DraftAnswer, Evidence, EvidenceSpan


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

    def add_excerpt(self, document: Document, tool_call_id: str, start: int, end: int,
                    *, heading_span: tuple[int, int] | None = None) -> Evidence:
        """Record exact returned spans, never concatenate a detached title into a quote."""
        spans = [(start, end)]
        if heading_span is not None and not (start <= heading_span[0] < heading_span[1] <= end):
            spans.append(heading_span)
        if any(not 0 <= a < b <= len(document.body) for a, b in spans):
            raise ValueError("Evidence spans must belong to the source document")
        item = Evidence(evidence_id=f"{self.run_id}:E{len(self._items) + 1}", tool_call_id=tool_call_id,
                        corpus_hash=self.corpus_hash, doc_id=document.doc_id, title=document.title,
                        version_date=document.version_date, content_hash=fingerprint(document.body),
                        start=start, end=end, text=document.body[start:end],
                        source_spans=[EvidenceSpan(start=a, end=b, text=document.body[a:b]) for a, b in spans])
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
            texts = [span.text for span in item.source_spans] if item.source_spans else [item.text]
            if citation.doc_id != item.doc_id or not any(citation.quote in text for text in texts):
                raise ValueError(f"citations.{index}：引用文档不匹配，或引文不是对应原文的连续片段。")

    def snapshot(self) -> list[Evidence]:
        return [item.model_copy(deep=True) for item in self._items.values()]

    def sources(self) -> list[dict]:
        """Deduplicate delivered exact spans; keep every source, including conflicts."""
        sources, seen = [], set()
        for item in self._items.values():
            if not item.delivered_to_model:
                continue
            for index, span in enumerate(item.source_spans or [item]):
                key = (item.doc_id, item.content_hash, span.start, span.end)
                if key in seen:
                    continue
                seen.add(key)
                sources.append(dict(source_id=f"{item.evidence_id}:S{index}",
                                    evidence_id=item.evidence_id, doc_id=item.doc_id,
                                    title=item.title, version_date=item.version_date.isoformat(),
                                    start=span.start, end=span.end, text=span.text))
        return sources

    def materialize(self, draft: DraftAnswer) -> Answer:
        """Resolve IDs to original text, without generating or changing business prose."""
        sources = {s["source_id"]: s for s in self.sources()}
        citations, parts, numbers = [], [], {}
        for part in draft.parts:
            refs = []
            for source_id in dict.fromkeys(part.source_ids):
                source = sources.get(source_id)
                if source is None:
                    raise ValueError("source_ids 必须选择本轮证据包中存在的 source_id。")
                if source_id not in numbers:
                    citations.append(Citation(evidence_id=source["evidence_id"],
                                              doc_id=source["doc_id"], quote=source["text"]))
                    numbers[source_id] = len(citations)
                refs.append(numbers[source_id])
            parts.append(AnswerPart(text=part.text, citation_numbers=refs))
        answer = Answer(answer="\n\n".join(p.text for p in parts), citations=citations,
                        answer_parts=parts, **draft.model_dump(exclude={"parts"}))
        self.validate(answer)
        return answer
