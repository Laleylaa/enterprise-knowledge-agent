"""Single-turn coordination; reusable by CLI and later evaluation entry points."""

import asyncio
from time import monotonic
from uuid import uuid4

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from knowledge_agent.agent import build_agent
from knowledge_agent.config import Settings
from knowledge_agent.context import TurnContext
from knowledge_agent.corpus import KnowledgeSource
from knowledge_agent.errors import RunStopped
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.model_adapter import RecordedModel, open_model
from knowledge_agent.schemas import Answer, RunResult, Usage
from knowledge_agent.trace import RunRecorder


def incomplete(message: str) -> Answer:
    return Answer(status="incomplete", answer=message, citations=[],
                  gaps=["当前问题的回答或查证尚未完成。"], clarification=None,
                  decision_summary="程序记录执行中断事实，未生成后续模型决策。")


async def run_turn(question: str, settings: Settings, source: KnowledgeSource) -> RunResult:
    if not question.strip() or len(question) > settings.max_input_chars:
        raise ValueError("问题不能为空，且不得超过配置的字符上限。")
    started = monotonic()
    run_id = uuid4().hex
    recorder = RunRecorder(settings.output_dir / settings.mode / run_id, run_id)
    state = TurnContext(settings, source, EvidenceStore(run_id, source.corpus_hash), recorder, Usage())
    recorder.write("input.json", {"question": question, "effective_history": [], "config": settings.public_config()})
    recorder.write("corpus.json", {"corpus_hash": source.corpus_hash, "documents": source.snapshot()})
    recorder.event("input_accepted")
    origin = "model" if settings.mode == "real" else "mock"
    reason = "completed"
    cancelled = False
    try:
        async with asyncio.timeout(settings.turn_timeout):
            async with open_model(settings) as model:
                agent = build_agent(RecordedModel(model, state), state)
                result = await agent.run(question, deps=state,
                                         usage_limits=UsageLimits(request_limit=settings.max_model_turns))
                answer = result.output
    except RunStopped as exc:
        reason, origin, answer = exc.reason, "runtime_fallback", incomplete(str(exc))
    except TimeoutError:
        reason, origin, answer = "turn_timeout", "runtime_fallback", incomplete("达到整轮时间上限，处理尚未完成。")
    except (UnexpectedModelBehavior, UsageLimitExceeded) as exc:
        recorder.event("framework_stopped", error_type=type(exc).__name__)
        reason, origin, answer = "protocol_or_budget_limit", "runtime_fallback", incomplete("模型输出无法接受或执行预算耗尽。")
    except asyncio.CancelledError:
        cancelled = True
        reason, origin, answer = "user_cancelled", "runtime_fallback", incomplete("用户取消了本轮处理。")
    except OSError:
        # Artifact failures must reach the CLI, not masquerade as a model failure.
        raise
    except Exception as exc:
        recorder.event("runtime_error", error_type=type(exc).__name__)
        reason, origin, answer = "runtime_error", "runtime_fallback", incomplete("运行发生内部错误，处理尚未完成。")
    outcome = RunResult(run_id=run_id, mode=settings.mode, result_origin=origin,
                        termination_reason=reason, result=answer,
                        observed_evidence=state.evidence.snapshot(), usage=state.usage)
    recorder.event("final_result", status=answer.status, termination_reason=reason, result_origin=origin)
    recorder.write("output.json", outcome.model_dump(mode="json"))
    recorder.write("run-summary.json", {"run_id": run_id, "elapsed_seconds": monotonic() - started,
                                       "usage": state.usage.model_dump(), "artifacts_saved": True,
                                       "mode": settings.mode, "stage": "integration_smoke"})
    if cancelled:
        raise asyncio.CancelledError
    return outcome
