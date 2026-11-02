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
    # Select evidence before composing claims; the public fields and types stay the same.
    citations: list[Citation] = Field(description="逐项支持 answer 中所有制度性结论的本轮原文；只引用实际需要的连续片段。状态结论须引状态定义，不能用文档用途或期限条款替代。")
    answer: NonEmpty = Field(description="仅用已选引文回答本轮所问及必要适用条件。逐句核对并删去无关提醒；每个保留的制度结论都必须被 citations 支持。原文出现但当前未问的相邻条款不展开，不推断用户未提供的事实。")
    gaps: list[NonEmpty] = Field(description="仅列本轮已问但尚未回答的事项，或阻碍必要核实的实际故障；未询问的日期、材料、状态等不列入。无相关缺口时为空列表。")
    clarification: NonEmpty | None = Field(description="为解决当前问题所需的具体追问；用户已说明没有更多可核实线索时为 null，不在 answer 中重复追问。")
    status: Status = Field(description="resolved：本轮所问均有依据；needs_info：需具体追问；unresolved：合理查证后仍缺依据或冲突无法确定；incomplete：实际故障或执行限制阻断必要处理。工具部分失败但证据充分时仍可 resolved。")
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
    mock_scenario: str | None = None
    run_id: str
    mode: Literal["real", "mock"]
    stage: Literal["integration_smoke", "tool_integration"] = "integration_smoke"
    requested_retrieval: Literal["smoke_fixture", "bm25", "vector", "hybrid"] = "smoke_fixture"
    result_origin: Literal["model", "mock", "runtime_fallback"]
    termination_reason: str
    result: Answer
    observed_evidence: list[Evidence]
    session_id: str | None = None
    turn_id: int | None = None
    previous_run_id: str | None = None
    action_summaries: list[dict] = Field(default_factory=list)
    usage: Usage
