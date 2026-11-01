"""Shared output correction policy; framework hooks still parse and feed back errors."""

from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability, RawOutput
from pydantic_ai.output import OutputContext

from knowledge_agent.context import TurnContext
from knowledge_agent.errors import RunStopped

MIXED_OUTPUT_REASON = "本次结果未被接受；请观察同批工具反馈后决定继续调用工具或单独提交最终结果。"


def reject_output(state: TurnContext, reason: str, kind: str) -> None:
    """Reserve one correction for this response, shared by all validation paths.

    A mixed response is reserved before its tools are admitted. Its later output
    hook must not charge the same response a second time. Successful tool calls
    never reset this run-scoped counter.
    """
    turn = state.usage.model_turns
    if state.rejected_output_turn == turn:
        return
    state.recorder.event("validation_failed", model_turn=turn, kind=kind, reason=reason)
    if state.output_retries_used >= state.settings.output_retries:
        state.recorder.event("output_retry_limit", model_turn=turn,
                             corrections_used=state.output_retries_used)
        raise RunStopped("output_retry_limit", "输出校验修正次数已耗尽，处理尚未完成。")
    state.output_retries_used += 1
    state.rejected_output_turn = turn
    state.recorder.event("output_correction_reserved", model_turn=turn,
                         correction=state.output_retries_used, kind=kind)


class OutputValidationPolicy(AbstractCapability[TurnContext]):
    async def before_output_validate(
        self, ctx: RunContext[TurnContext], *, output_context: OutputContext, output: RawOutput,
    ) -> RawOutput:
        if ctx.deps.mixed_response:
            # Already reserved at the model response boundary, before tool execution.
            raise ModelRetry(MIXED_OUTPUT_REASON)
        return output

    async def on_output_validate_error(
        self, ctx: RunContext[TurnContext], *, output_context: OutputContext,
        output: RawOutput, error: ValidationError | ModelRetry,
    ):
        if isinstance(error, ValidationError):
            reason = "; ".join(
                f"{'.'.join(map(str, item['loc'])) or 'result'}: {item['msg']}"
                for item in error.errors(include_input=False, include_url=False)
            )
        else:
            reason = str(error)
        reject_output(ctx.deps, reason, "structure")
        # PydanticAI supplies its field-level validation feedback; do not fix the answer here.
        raise error
