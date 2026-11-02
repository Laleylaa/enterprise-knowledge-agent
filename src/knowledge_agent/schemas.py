"""Framework-independent data exchanged by the CLI, tools and runtime."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonEmpty = Annotated[str, Field(min_length=1, pattern=r"\S")]
Status = Literal["resolved", "needs_info", "unresolved", "incomplete"]
STATUS_DESCRIPTION = (
    "resolved：本问有充分原文依据；needs_info：缺最小必要用户信息，需具体追问；"
    "unresolved：工具正常完成必要查证后仍缺依据或冲突未解，或问题超出服务范围；"
    "incomplete：实际故障或执行限制阻断必要处理。blocked且必要工具持续失败、证据不足时必须用incomplete，不能用unresolved。"
    "正常返回空结果不等于执行故障；部分失败或失败后恢复但证据充分时仍可resolved。"
)


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


class ResearchComplete(StrictModel):
    reason: Literal["unclear_question", "sufficient", "needs_user", "missing", "blocked", "out_of_scope"] = Field(
        description="对象不明且历史无法解释：unclear_question，不调用工具；对象明确但缺用户条件：needs_user；正常查证后缺依据：missing；实际故障阻断必要查证：blocked；其余按取证规则选择。")
    decision_summary: NonEmpty = Field(description="只说明结束取证的原因，不改写原文或生成业务答案。")


class EvidenceRequest(StrictModel):
    question: NonEmpty = Field(description="阻止回答当前问题的具体证据缺口；交给取证阶段查证，不猜测工具参数。")


class DraftPart(StrictModel):
    text: NonEmpty = Field(description="用户可见正文：只回答本问，忠实摘录或压缩原文；禁止写入内部source_id、evidence_id、tool_call_id或run_id，不自行添加引用标记。可用D01等公开文档ID区分制度。全部制度结论及必要条件须由本段source_ids支持，不添加因果、例外或规则影响关系。")
    source_ids: list[NonEmpty] = Field(description="内部来源ID只填写在此数组，选择证据包中的source_id；不得抄到text、gaps或clarification。程序生成引用原文与序号，不抄写或改写引文。纯用户转述、缺口说明或追问可为空。")


class DraftAnswer(StrictModel):
    parts: list[DraftPart] = Field(min_length=1)
    gaps: list[NonEmpty] = Field(description="用户可见：只列阻止回答本轮问题的必要缺口，不包含内部来源ID或运行ID；公司制度天数不明不等于需要个人剩余额度。")
    clarification: NonEmpty | None = Field(description="用户可见的最小必要追问，不包含内部来源ID或运行ID；无需追问时为null。")
    status: Status = Field(description=STATUS_DESCRIPTION)
    decision_summary: NonEmpty


class AnswerPart(StrictModel):
    text: NonEmpty
    citation_numbers: list[int]


class Answer(StrictModel):
    # Public result: citations and paragraph links are materialized by the program.
    citations: list[Citation] = Field(description="逐项支持 answer 中所有制度性结论的本轮原文；只引用实际需要的连续片段。状态结论须引状态定义，不能用文档用途或期限条款替代。")
    answer: NonEmpty = Field(description="直接回答本轮所问及必要条件。制度结论由已选引文支持；用户陈述忠实归属于用户，不补充未知细节。条款存在不等于适用于当前情况；无法核实不等于通知无效。省略无关提醒。")
    gaps: list[NonEmpty] = Field(description="准确指出本轮缺少的条款内容、适用/替代关系、用户条件或必要查证的故障。已有条款但适用性未知时只写缺适用关系，不能否认条款存在。无相关缺口时为空列表。")
    clarification: NonEmpty | None = Field(description="为解决当前问题所需的具体追问；用户已说明没有更多可核实线索时为 null，不在 answer 中重复追问。")
    status: Status = Field(description=STATUS_DESCRIPTION)
    decision_summary: NonEmpty
    answer_parts: list[AnswerPart] = Field(default_factory=list)

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
