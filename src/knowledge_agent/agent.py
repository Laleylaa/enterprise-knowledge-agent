"""PydanticAI composition and output validation, separate from transport and CLI."""

from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.models import Model

from knowledge_agent.context import TurnContext
from knowledge_agent.execution_policy import ToolExecutionPolicy
from knowledge_agent.output_validation import OutputValidationPolicy, reject_output
from knowledge_agent.schemas import Answer
from knowledge_agent.tools import read_document, search_knowledge

INSTRUCTIONS = """
你是员工制度问答助手。本次是接入冒烟，工具资料为合成资料。
根据当前问题自主选择检索或读取工具，再依据实际工具结果决定继续或结束。
无需制度依据即可提出必要澄清时，可以直接提交澄清结果；不强制先调用工具。
制度结论必须依据本轮工具取得的原文；不要凭常识、用户声明或历史回答补充制度。
候选资料可能无关；资料不足时说明缺口，必要条件不明时提出具体澄清。
发现无法解释的冲突时继续查证，不凭日期或数值擅自选择规定。
引用必须使用工具返回的 evidence_id、doc_id 和原文连续片段。
所有诉求有依据才 resolved；具体追问用 needs_info；无依据且无具体追问用 unresolved；
必要处理被故障中断用 incomplete。工具失败不等于资料不存在。
工具调用和最终结果应分开提交，先观察工具结果再决定是否结束。
purpose 和 decision_summary 只写简短行动依据，不输出内部思维过程。
""".strip()


def build_agent(model: Model, state: TurnContext) -> Agent[TurnContext, Answer]:
    agent = Agent(
        model,
        deps_type=TurnContext,
        output_type=ToolOutput(Answer, name="submit_answer", max_retries=state.settings.output_retries),
        instructions=INSTRUCTIONS,
        retries=state.settings.output_retries,
        end_strategy="graceful",
        # The application deadline returns a structured error; the framework's
        # default timeout instead consumes its parameter/ModelRetry allowance.
        capabilities=[OutputValidationPolicy(), ToolExecutionPolicy()],
    )
    agent.tool(search_knowledge, sequential=True)
    agent.tool(read_document, sequential=True)

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
