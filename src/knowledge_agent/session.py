"""Ephemeral conversation text, explicit import and per-turn provenance.

Saved history is an audit/export artifact; no startup code discovers or resumes it.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, ValidationError
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from knowledge_agent.presentation import render_result
from knowledge_agent.schemas import NonEmpty, RunResult, StrictModel


class HistoryInputError(ValueError):
    pass


class HistoryMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: NonEmpty


class HistoryFile(StrictModel):
    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)]
    messages: list[HistoryMessage]


class HistoryEntry(HistoryMessage):
    origin: Literal["imported", "session"]
    run_id: str | None = None
    source_hash: str | None = None
    source_index: int | None = None


def validate_input(question: str, history: list[HistoryEntry], limit: int) -> None:
    if not question.strip():
        raise HistoryInputError("问题不能为空，请重新输入。")
    if len(question) + sum(len(m.content) for m in history) > limit:
        raise HistoryInputError("问题与历史合计超过字符上限；请提供较短历史或退出后开始新会话。历史未被截断。")


def load_history(path: Path, limit: int) -> tuple[list[HistoryEntry], dict]:
    # JSON unicode escapes need up to 12 bytes per character; also bound envelope whitespace.
    with path.open("rb") as stream:
        raw = stream.read(limit * 12 + 65537)
    if len(raw) > limit * 12 + 65536:
        raise HistoryInputError("历史文件体积超过上限，请提供较短历史。")
    try:
        document = HistoryFile.model_validate_json(raw)
    except ValidationError as exc:
        raise HistoryInputError("历史格式不合法：要求 schema_version=1，messages 仅含非空 user／assistant 文本，不接受其他角色或字段。") from exc
    if sum(len(m.content) for m in document.messages) > limit:
        raise HistoryInputError("历史内容超过字符上限，请提供较短历史；不会自动摘要或截断。")
    digest = hashlib.sha256(raw).hexdigest()
    entries = [HistoryEntry(**m.model_dump(), origin="imported", source_hash=digest, source_index=i)
               for i, m in enumerate(document.messages)]
    return entries, {"source_path": str(path), "source_hash": digest, "history": document.model_dump()}


@dataclass(frozen=True)
class SessionTurn:
    session_id: str
    turn_id: int
    previous_run_id: str | None
    effective_history: list[HistoryEntry]

    def messages(self):
        return [ModelRequest(parts=[UserPromptPart(m.content)]) if m.role == "user" else
                ModelResponse(parts=[TextPart(m.content)]) for m in self.effective_history]

    def metadata(self):
        return {"session_id": self.session_id, "turn_id": self.turn_id, "previous_run_id": self.previous_run_id,
                "effective_history": [m.model_dump() for m in self.effective_history]}


@dataclass
class ConversationSession:
    session_id: str = field(default_factory=lambda: uuid4().hex)
    history: list[HistoryEntry] = field(default_factory=list)
    turn_id: int = 0
    previous_run_id: str | None = None
    active_run_id: str | None = None

    def prepare(self, question: str, limit: int) -> SessionTurn:
        if self.active_run_id is not None:
            raise RuntimeError("This session already has an active turn")
        validate_input(question, self.history, limit)
        return SessionTurn(self.session_id, self.turn_id + 1, self.previous_run_id,
                           [m.model_copy(deep=True) for m in self.history])

    def accept(self, question: str, run_id: str, turn: SessionTurn):
        if turn.session_id != self.session_id or turn.turn_id != self.turn_id + 1 or self.active_run_id:
            raise RuntimeError("Stale or overlapping session turn")
        self.turn_id = turn.turn_id
        self.active_run_id = run_id
        self.history.append(HistoryEntry(role="user", content=question, origin="session", run_id=run_id))

    def finish(self, result: RunResult):
        if result.run_id != self.active_run_id:
            raise RuntimeError("Result does not belong to active session turn")
        # Only final presented conversation text crosses turns, never raw tool/retry messages.
        self.history.append(HistoryEntry(role="assistant", content=render_result(result),
                                         origin="session", run_id=result.run_id))
        self.previous_run_id = result.run_id
        self.active_run_id = None

    def export(self):
        return {"schema_version": 1, "messages": [{"role": m.role, "content": m.content} for m in self.history]}

    def clear(self):
        self.history.clear()
        self.active_run_id = None
        self.previous_run_id = None
