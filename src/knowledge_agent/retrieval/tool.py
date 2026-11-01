"""Single search tool: validate, rank/locate, page, record exact evidence."""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Annotated

from pydantic import Field, ValidationError, model_validator

from knowledge_agent.config import Settings
from knowledge_agent.corpus import fingerprint
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.schemas import NonEmpty, StrictModel
from knowledge_agent.trace import RunRecorder
from knowledge_agent.retrieval.bm25 import Bm25Index
from knowledge_agent.retrieval.models import Chunk, digest


class SearchRequest(StrictModel):
    query: str = Field(description="检索问题；仅按明确 doc_ids 定位时允许为空。")
    purpose: NonEmpty = Field(description="简短行动目的，仅记录，不影响排序。")
    doc_ids: list[NonEmpty] | None = Field(default=None, description="限定的文档 ID；不能为空列表；重复项按首次出现去重。")
    limit: Annotated[int, Field(strict=True, ge=1, le=10)] = Field(default=5, description="每页块数，1 到 10。")
    cursor: str | None = Field(default=None, description="上页返回的不透明游标；保持 query、doc_ids 和 limit 不变。")

    @model_validator(mode="after")
    def meaningful_query_or_ids(self):
        if self.doc_ids == [] or (not self.query.strip() and self.doc_ids is None):
            raise ValueError("Provide a nonempty query or explicit document IDs")
        return self


@dataclass(frozen=True)
class CursorPage:
    binding: str
    candidates: tuple[Chunk, ...]
    offset: int
    strategy: str
    errors: tuple[dict, ...]


def tool_error(code: str, message: str, *, retryable: bool = False,
               kind: str | None = None, identity: str | None = None) -> dict:
    return {"code": code, "message": message, "retryable": retryable,
            "target": {"kind": kind, "id": identity} if kind else None}


class SearchTool:
    name = "search_knowledge"
    description = "按关键词检索原文块；可过滤文档、按明确 ID 定位或沿游标翻页。候选不代表结论。"

    def __init__(self, index: Bm25Index, settings: Settings, evidence: EvidenceStore, recorder: RunRecorder,
                 *, standalone: bool = True):
        if evidence.corpus_hash != index.snapshot.corpus_hash:
            raise ValueError("Evidence store and index must use the same snapshot")
        self.index, self.settings, self.evidence, self.recorder = index, settings, evidence, recorder
        self.standalone = standalone
        self._cursors: OrderedDict[str, CursorPage] = OrderedDict()

    def execute(self, arguments: dict, *, call_id: str) -> dict:
        """call_id is supplied by the caller, never included in model arguments."""
        recorded_input = {"tool": self.name, "tool_call_id": call_id, "arguments": arguments}
        self.recorder.append("tool-inputs.jsonl", recorded_input)
        if self.standalone:
            self.recorder.write("input.json", recorded_input)
            self.recorder.event("tool_started", tool=self.name, tool_call_id=call_id, arguments=arguments)
        try:
            request = SearchRequest.model_validate(arguments)
        except ValidationError:
            return self._return(call_id, "error", errors=[tool_error("INVALID_ARGUMENT", "搜索参数不符合契约，请检查 query、purpose、doc_ids、limit、cursor。")])
        doc_ids = tuple(dict.fromkeys(request.doc_ids)) if request.doc_ids is not None else None
        binding = digest({"tool": self.name, "corpus": self.index.snapshot.corpus_hash,
                          "index": self.index.index_hash, "query": request.query, "doc_ids": doc_ids,
                          "limit": request.limit, "max_chars": self.settings.max_tool_chars})
        if request.cursor is not None:
            page = self._cursors.get(request.cursor)
            if page is None or page.binding != binding:
                return self._return(call_id, "error", errors=[tool_error("INVALID_CURSOR", "游标无效、已失效或与本次参数不匹配。",
                                                                         kind="cursor", identity=request.cursor)])
        else:
            errors = []
            valid_ids = None
            if doc_ids is not None:
                valid_ids = tuple(doc_id for doc_id in doc_ids if self.index.snapshot.get(doc_id) is not None)
                errors = [tool_error("NOT_FOUND", "文档 ID 不在本次资料快照中。", kind="doc", identity=doc_id)
                          for doc_id in doc_ids if doc_id not in valid_ids]
                if not valid_ids:
                    return self._return(call_id, "error", strategy="id_lookup" if not request.query.strip() else "bm25", errors=errors)
            strategy = "bm25" if request.query.strip() else "id_lookup"
            try:
                candidates = self.index.rank(request.query, valid_ids) if strategy == "bm25" else self.index.lookup(valid_ids)
            except Exception as exc:
                self.recorder.event("retrieval_failed", tool_call_id=call_id, error_type=type(exc).__name__)
                errors.append(tool_error("SEARCH_FAILED", "本次检索执行失败，未能取得候选。", retryable=True,
                                         kind="branch", identity=strategy))
                return self._return(call_id, "error", strategy=strategy, errors=errors)
            page = CursorPage(binding, tuple(candidates), 0, strategy, tuple(errors))
        selected, used, offset, limited = [], 0, page.offset, False
        while offset < len(page.candidates) and len(selected) < request.limit:
            chunk = page.candidates[offset]
            section = self.index.snapshot.sections[chunk.section_id]
            size = len(chunk.text) + len(section.heading or "")
            if used + size > self.settings.max_tool_chars:
                limited = True
                break
            selected.append(chunk)
            used += size
            offset += 1
        if not selected and offset < len(page.candidates):
            return self._return(call_id, "error", strategy=page.strategy, errors=[*page.errors, tool_error(
                "RETURN_BUDGET_TOO_SMALL", "正文预算无法容纳首块及其标题，请调整配置。")], limited=True,
                branches=["bm25"] if page.strategy == "bm25" else [])
        hits = [self._hit(chunk, call_id) for chunk in selected]
        cursor = None
        if offset < len(page.candidates):
            cursor = token_urlsafe(24)
            self._cursors[cursor] = CursorPage(binding, page.candidates, offset, page.strategy, page.errors)
            while len(self._cursors) > self.settings.search_cursor_capacity:
                self._cursors.popitem(last=False)
        status = "partial" if page.errors else "ok" if hits else "empty"
        return self._return(call_id, status, hits=hits, strategy=page.strategy, errors=list(page.errors),
                            cursor=cursor, limited=limited, branches=["bm25"] if page.strategy == "bm25" else [])

    def _hit(self, chunk: Chunk, call_id: str) -> dict:
        snapshot = self.index.snapshot
        document = snapshot.get(chunk.doc_id)
        assert document is not None
        section = snapshot.sections[chunk.section_id]
        heading = section.heading_span
        evidence = self.evidence.add_excerpt(document, call_id, chunk.start, chunk.end,
                                             heading_span=(heading.start, heading.end) if heading else None)
        return {"evidence_id": evidence.evidence_id, "doc_id": document.doc_id, "title": document.title,
                "version_date": document.version_date.isoformat(), "content_hash": fingerprint(document.body),
                "section_id": chunk.section_id, "section_heading": section.heading,
                "heading_span": heading.model_dump() if heading else None, "chunk_id": chunk.chunk_id,
                "source_span": {"start": chunk.start, "end": chunk.end}, "text": chunk.text}

    def _return(self, call_id, status, *, hits=None, strategy="bm25", errors=None,
                cursor=None, limited=False, branches=None) -> dict:
        response = {"schema_version": 1, "tool": self.name, "tool_call_id": call_id,
                    "corpus_hash": self.index.snapshot.corpus_hash, "status": status,
                    "data": {"hits": hits or [], "segments": [], "locators": []}, "errors": deepcopy(errors or []),
                    "execution": {"strategy": strategy, "requested_mode": "bm25",
                                  "effective_branches": branches or [],
                                  "next_cursor": cursor, "has_more": cursor is not None, "return_limited": limited}}
        self.recorder.append("tool-results.jsonl", response)
        self.recorder.event("tool_result", tool=self.name, tool_call_id=call_id, status=status,
                             doc_ids=[h["doc_id"] for h in response["data"]["hits"]],
                             error_codes=[e["code"] for e in response["errors"]])
        if self.standalone:
            self.recorder.write("output.json", response)
        self.recorder.write("observed-evidence.json", [e.model_dump(mode="json") for e in self.evidence.snapshot()])
        return response
