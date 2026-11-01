"""Framework-independent data exchanged by the CLI, tools and runtime."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonEmpty = Annotated[str, Field(min_length=1, pattern=r"\S")]
Status = Literal["resolved", "needs_info", "unresolved", "incomplete"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Document(StrictModel):
    doc_id: NonEmpty
    title: NonEmpty
    version_date: date
    body: NonEmpty


class Citation(StrictModel):
    evidence_id: NonEmpty
    doc_id: NonEmpty
    quote: NonEmpty


class Answer(StrictModel):
    status: Status
    answer: NonEmpty
    citations: list[Citation]
    gaps: list[NonEmpty]
    clarification: NonEmpty | None
    decision_summary: NonEmpty

    @model_validator(mode="after")
    def consistent_fields(self) -> "Answer":
        if self.status == "needs_info" and self.clarification is None:
            raise ValueError("needs_info requires clarification")
        if self.status == "resolved" and (self.gaps or self.clarification or not self.citations):
            raise ValueError("resolved requires citations, no gaps and no clarification")
        if self.status == "unresolved" and self.clarification is not None:
            raise ValueError("unresolved cannot request clarification")
        return self


class EvidenceSpan(StrictModel):
    start: int
    end: int
    text: str


class Evidence(StrictModel):
    evidence_id: str
    tool_call_id: str
    corpus_hash: str
    doc_id: str
    title: str
    version_date: date
    content_hash: str
    start: int
    end: int
    text: str
    source_spans: list[EvidenceSpan] = Field(default_factory=list)
    delivered_to_model: bool = False


class Usage(StrictModel):
    model_turns: int = 0
    http_attempts: int = 0
    tool_calls: int = 0


class RunResult(StrictModel):
    run_id: str
    mode: Literal["real", "mock"]
    stage: Literal["integration_smoke"] = "integration_smoke"
    requested_retrieval: Literal["smoke_fixture"] = "smoke_fixture"
    result_origin: Literal["model", "mock", "runtime_fallback"]
    termination_reason: str
    result: Answer
    observed_evidence: list[Evidence]
    usage: Usage
