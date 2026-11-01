"""Read exact source ranges using the same snapshot and evidence contract as search."""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from secrets import token_urlsafe

from pydantic import Field, ValidationError, model_validator

from knowledge_agent.config import Settings
from knowledge_agent.corpus import fingerprint
from knowledge_agent.errors import CorpusError
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.retrieval.models import digest
from knowledge_agent.retrieval.snapshot import RetrievalSnapshot
from knowledge_agent.schemas import NonEmpty, StrictModel
from knowledge_agent.trace import RunRecorder


class ReadRequest(StrictModel):
    doc_id: NonEmpty = Field(description="原文文档 ID；单独提供时读取全文。")
    purpose: NonEmpty = Field(description="简短读取目的，只记日志，不改变所读内容。")
    section_id: NonEmpty | None = Field(default=None, description="读取所属章节标题及正文；与 chunk_id 互斥。")
    chunk_id: NonEmpty | None = Field(default=None, description="只读取指定块及所属标题，不自动扩展到章节。")
    cursor: str | None = Field(default=None, description="超大读取的定位列表续页；保持选择器不变，不能用于读取正文。")

    @model_validator(mode="after")
    def exclusive_selector(self):
        if self.section_id is not None and self.chunk_id is not None:
            raise ValueError("section_id and chunk_id are mutually exclusive")
        return self


def error(code, message, *, kind=None, identity=None, retryable=False):
    return {"code": code, "message": message, "retryable": retryable,
            "target": {"kind": kind, "id": identity} if kind else None}


class ReadFailure(Exception):
    def __init__(self, detail):
        self.detail = detail


@dataclass(frozen=True)
class LocatorPage:
    binding: str
    locators: tuple[dict, ...]
    offset: int
    strategy: str


class ReadTool:
    name = "read_document"
    description = "按文档、章节或块读取原文；扩大到章节须传 section_id。超大内容仅返回局部读取定位。"
    locator_page_size = 20

    def __init__(self, snapshot: RetrievalSnapshot, settings: Settings,
                 evidence: EvidenceStore, recorder: RunRecorder, *, standalone: bool = True):
        if evidence.corpus_hash != snapshot.corpus_hash:
            raise ValueError("Evidence store and reader must use the same snapshot")
        if any(len(c.text) + len(snapshot.sections[c.section_id].heading or "") > settings.max_tool_chars
               for c in snapshot.chunks):
            raise CorpusError("返回正文预算无法容纳单块及其标题，请调整 max_tool_chars 或重新 prepare。")
        self.snapshot, self.settings = snapshot, settings
        self.evidence, self.recorder = evidence, recorder
        self.standalone = standalone
        self._cursors: OrderedDict[str, LocatorPage] = OrderedDict()

    def execute(self, arguments: dict, *, call_id: str) -> dict:
        recorded = {"tool": self.name, "tool_call_id": call_id, "arguments": arguments}
        self.recorder.append("tool-inputs.jsonl", recorded)
        if self.standalone:
            self.recorder.write("input.json", recorded)
            self.recorder.event("tool_started", **recorded)
        try:
            request = ReadRequest.model_validate(arguments)
        except ValidationError:
            return self._return(call_id, "document", errors=[error(
                "INVALID_ARGUMENT", "读取参数不符合契约；提供 doc_id、purpose，section_id 与 chunk_id 互斥。")])
        strategy = "chunk" if request.chunk_id is not None else "section" if request.section_id is not None else "document"
        binding = digest({"tool": self.name, "corpus_hash": self.snapshot.corpus_hash,
                          "doc_id": request.doc_id, "section_id": request.section_id, "chunk_id": request.chunk_id,
                          "max_chars": self.settings.max_tool_chars, "page_size": self.locator_page_size})
        if request.cursor is not None:
            page = self._cursors.get(request.cursor)
            if page is None or page.binding != binding:
                return self._return(call_id, strategy, errors=[error(
                    "INVALID_CURSOR", "游标无效、已失效或与读取选择器不匹配。", kind="cursor", identity=request.cursor)])
            return self._locator_result(call_id, request, page)
        # Only source access is translated into READ_FAILED. Recording failures propagate.
        try:
            document, spans, locators = self._select(request)
        except ReadFailure as exc:
            return self._return(call_id, strategy, errors=[exc.detail])
        except Exception as exc:
            self.recorder.event("read_failed", tool_call_id=call_id, error_type=type(exc).__name__)
            return self._return(call_id, strategy, errors=[error(
                "READ_FAILED", "本次原文读取失败，未能取得正文。", kind="doc", identity=request.doc_id, retryable=True)])
        # Count the same returned text and heading fields as search, including any duplication.
        size = sum(end - start + len(section.heading or "") for section, start, end, _ in spans)
        if size > self.settings.max_tool_chars:
            if strategy == "chunk":
                return self._return(call_id, strategy, errors=[error(
                    "RETURN_BUDGET_TOO_SMALL", "当前预算无法容纳该块及其标题，请调整配置。")], limited=True)
            return self._locator_result(call_id, request, LocatorPage(binding, tuple(locators), 0, strategy))
        segments = []
        for section, start, end, chunk_id in spans:
            heading = section.heading_span
            item = self.evidence.add_excerpt(document, call_id, start, end,
                                             heading_span=(heading.start, heading.end) if heading else None)
            segments.append({"evidence_id": item.evidence_id, "doc_id": document.doc_id,
                             "title": document.title, "version_date": document.version_date.isoformat(),
                             "content_hash": fingerprint(document.body), "section_id": section.section_id,
                             "section_heading": section.heading,
                             "heading_span": heading.model_dump() if heading else None,
                             "chunk_id": chunk_id, "source_span": {"start": start, "end": end},
                             "text": document.body[start:end]})
        return self._return(call_id, strategy, segments=segments)

    def _select(self, request):
        document = self.snapshot.get(request.doc_id)
        if document is None:
            raise ReadFailure(error("NOT_FOUND", "文档 ID 不在本次资料快照中。", kind="doc", identity=request.doc_id))
        selected_sections = [s for s in self.snapshot.sections.values() if s.doc_id == request.doc_id]
        selected_chunks = [c for c in self.snapshot.chunks if c.doc_id == request.doc_id]
        if request.section_id is not None or request.chunk_id is not None:
            kind = "section" if request.section_id is not None else "chunk"
            identity = request.section_id if kind == "section" else request.chunk_id
            selected = (self.snapshot.sections.get(identity) if kind == "section" else
                        next((c for c in self.snapshot.chunks if c.chunk_id == identity), None))
            if selected is None:
                raise ReadFailure(error("NOT_FOUND", "指定章节或块不在本次资料快照中。", kind=kind, identity=identity))
            if selected.doc_id != request.doc_id:
                raise ReadFailure(error("INVALID_ARGUMENT", "指定章节或块不属于该文档。", kind=kind, identity=identity))
            if kind == "chunk":
                return document, [(self.snapshot.sections[selected.section_id], selected.start, selected.end, selected.chunk_id)], []
            selected_sections = [selected]
            selected_chunks = [c for c in selected_chunks if c.section_id == selected.section_id]
        spans = [(s, s.start, s.end, None) for s in selected_sections]
        locators = [{"doc_id": c.doc_id, "section_id": c.section_id, "chunk_id": c.chunk_id,
                     "source_span": {"start": c.start, "end": c.end},
                     "read_args": {"doc_id": c.doc_id, "chunk_id": c.chunk_id}} for c in selected_chunks]
        return document, spans, locators

    def _locator_result(self, call_id, request, page):
        end = min(page.offset + self.locator_page_size, len(page.locators))
        cursor = None
        if end < len(page.locators):
            cursor = token_urlsafe(24)
            self._cursors[cursor] = LocatorPage(page.binding, page.locators, end, page.strategy)
            while len(self._cursors) > self.settings.read_cursor_capacity:
                self._cursors.popitem(last=False)
        return self._return(call_id, page.strategy, errors=[error(
            "CONTENT_TOO_LARGE", "所选全文或章节超过正文预算；请按定位信息另行读取块。",
            kind="section" if request.section_id else "doc", identity=request.section_id or request.doc_id)],
            locators=deepcopy(list(page.locators[page.offset:end])), cursor=cursor, limited=True)

    def _return(self, call_id, strategy, *, segments=None, errors=None, locators=None, cursor=None, limited=False):
        result = {"schema_version": 1, "tool": self.name, "tool_call_id": call_id,
                  "corpus_hash": self.snapshot.corpus_hash, "status": "error" if errors else "ok",
                  "data": {"hits": [], "segments": segments or [], "locators": locators or []},
                  "errors": errors or [],
                  "execution": {"strategy": strategy, "requested_mode": None, "effective_branches": [],
                                "next_cursor": cursor, "has_more": cursor is not None, "return_limited": limited}}
        self.recorder.append("tool-results.jsonl", result)
        self.recorder.event("tool_result", tool=self.name, tool_call_id=call_id, status=result["status"],
                            doc_ids=list(dict.fromkeys(s["doc_id"] for s in result["data"]["segments"])),
                            error_codes=[e["code"] for e in result["errors"]])
        if self.standalone:
            self.recorder.write("output.json", result)
        self.recorder.write("observed-evidence.json", [e.model_dump(mode="json") for e in self.evidence.snapshot()])
        return result
