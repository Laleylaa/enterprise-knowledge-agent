"""Separate evidence collection and grounded answer generation with PydanticAI."""

from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.models import Model

from knowledge_agent.context import TurnContext
from knowledge_agent.execution_policy import ToolExecutionPolicy
from knowledge_agent.output_validation import OutputValidationPolicy, reject_output
from knowledge_agent.schemas import DraftAnswer, EvidenceRequest, ResearchComplete
from knowledge_agent.tools import read_document, search_knowledge
from knowledge_agent.tool_binding import register_knowledge_tools
from knowledge_agent.prompts import ANSWER_INSTRUCTIONS, INSTRUCTIONS, conversation_context


def build_agent(model: Model, state: TurnContext) -> Agent[TurnContext, ResearchComplete]:
    """The collector can fetch raw evidence or stop; it cannot write the final answer."""
    agent = Agent(
        model, deps_type=TurnContext,
        output_type=ToolOutput(ResearchComplete, name="finish_research",
                               max_retries=state.settings.output_retries,
                               description="结束本阶段取证，由程序向回答阶段传递全部已取得原文。"),
        instructions=INSTRUCTIONS, retries=state.settings.output_retries,
        end_strategy="graceful",
        capabilities=[OutputValidationPolicy(), ToolExecutionPolicy()],
    )
    if state.knowledge_tools is not None:
        register_knowledge_tools(agent)
    else:
        agent.tool(search_knowledge, sequential=True)
        agent.tool(read_document, sequential=True)

    @agent.instructions
    def conversation_boundary(ctx: RunContext[TurnContext]) -> str:
        remaining = ctx.deps.settings.max_model_turns - ctx.deps.usage.model_turns
        return (conversation_context(ctx.deps.history_message_count)
                + f" 当前剩余模型轮次 {remaining}，结束取证后回答阶段还需要至少 1 次调用。")

    @agent.output_validator
    def finish(ctx: RunContext[TurnContext], result: ResearchComplete) -> ResearchComplete:
        ctx.deps.recorder.event("research_complete", result=result.model_dump(mode="json"))
        return result

    return agent


def build_answer_agent(model: Model, state: TurnContext, *, allow_supplement: bool):
    outputs = [ToolOutput(DraftAnswer, name="submit_answer",
                          description="按段落组织答案并选择 source_ids，引用原文由程序生成。",
                          max_retries=state.settings.output_retries)]
    if allow_supplement:
        outputs.append(ToolOutput(EvidenceRequest, name="request_evidence",
                                  description="请求针对必要证据缺口补查一次，不能用于重复查证。",
                                  max_retries=state.settings.output_retries))
    agent = Agent(model, deps_type=TurnContext, output_type=outputs,
                  instructions=ANSWER_INSTRUCTIONS, retries=state.settings.output_retries,
                  capabilities=[OutputValidationPolicy()])

    @agent.output_validator
    def validate_answer(ctx: RunContext[TurnContext], result):
        if isinstance(result, EvidenceRequest):
            ctx.deps.recorder.event("evidence_requested", request=result.model_dump(mode="json"))
            return result
        ctx.deps.recorder.event("answer_draft", result=result.model_dump(mode="json"))
        try:
            answer = ctx.deps.evidence.materialize(result)
        except ValueError as exc:
            reject_output(ctx.deps, str(exc), "citation_or_status")
            raise ModelRetry(str(exc)) from exc
        ctx.deps.recorder.event("result_candidate", origin=ctx.deps.settings.mode,
                                result=answer.model_dump(mode="json"))
        return result

    return agent
