"""PydanticAI composition and output validation, separate from transport and CLI."""

from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.models import Model

from knowledge_agent.context import TurnContext
from knowledge_agent.execution_policy import ToolExecutionPolicy
from knowledge_agent.output_validation import OutputValidationPolicy, reject_output
from knowledge_agent.schemas import Answer
from knowledge_agent.tools import read_document, search_knowledge
from knowledge_agent.tool_binding import register_knowledge_tools
from knowledge_agent.prompts import ANSWER_DESCRIPTION, INSTRUCTIONS, conversation_context


def build_agent(model: Model, state: TurnContext) -> Agent[TurnContext, Answer]:
    agent = Agent(
        model,
        deps_type=TurnContext,
        output_type=ToolOutput(
            Answer, name="submit_answer", max_retries=state.settings.output_retries,
            description=ANSWER_DESCRIPTION,
        ),
        instructions=INSTRUCTIONS,
        retries=state.settings.output_retries,
        end_strategy="graceful",
        # The application deadline returns a structured error; the framework's
        # default timeout instead consumes its parameter/ModelRetry allowance.
        capabilities=[OutputValidationPolicy(), ToolExecutionPolicy()],
    )
    if state.knowledge_tools is not None:
        register_knowledge_tools(agent)
    else:
        # The explicit legacy smoke source remains available for existing baseline checks.
        agent.tool(search_knowledge, sequential=True)
        agent.tool(read_document, sequential=True)

    @agent.instructions
    def conversation_boundary(ctx: RunContext[TurnContext]) -> str:
        return conversation_context(ctx.deps.history_message_count)

    @agent.output_validator
    def validate_answer(ctx: RunContext[TurnContext], result: Answer) -> Answer:
        ctx.deps.recorder.event("result_candidate", origin=ctx.deps.settings.mode,
                                result=result.model_dump(mode="json"))
        try:
            ctx.deps.evidence.validate(result)
        except ValueError as exc:
            reject_output(ctx.deps, str(exc), "citation")
            raise ModelRetry(str(exc)) from exc
        return result

    return agent
