"""Single-turn coordination; reusable by CLI and later evaluation entry points."""

import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from time import monotonic
from uuid import uuid4

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import UsageLimits
from pydantic_ai.models import Model
from pydantic_ai.messages import ModelRequest, UserPromptPart

from knowledge_agent.agent import build_agent, build_answer_agent
from knowledge_agent.answering import answer_packet
from knowledge_agent.budgets import check_time
from knowledge_agent.config import Settings
from knowledge_agent.context import TurnContext
from knowledge_agent.corpus import KnowledgeSource
from knowledge_agent.errors import RunStopped, TurnCancelled
from knowledge_agent.knowledge_base import IndexedCorpus
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.model_adapter import RecordedModel, open_model
from knowledge_agent.schemas import Answer, EvidenceRequest, RunResult, Usage
from knowledge_agent.session import ConversationSession, SessionTurn, validate_input
from knowledge_agent.trace import RunRecorder
from knowledge_agent.tool_binding import KnowledgeTools

ModelFactory = Callable[[Settings], AbstractAsyncContextManager[Model]]


def incomplete(message: str) -> Answer:
    return Answer(status="incomplete", answer=message, citations=[],
                  gaps=["当前问题的回答或查证尚未完成。"], clarification=None,
                  decision_summary="程序记录执行中断事实，未生成后续模型决策。")


def create_turn_context(question: str, settings: Settings, source: KnowledgeSource | IndexedCorpus,
                        *, session_turn: SessionTurn | None = None) -> TurnContext:
    """Prepare real tools and run-scoped state without starting any model requests."""
    validate_input(question, session_turn.effective_history if session_turn else [], settings.max_input_chars)
    started = monotonic()
    run_id = uuid4().hex
    recorder = RunRecorder(settings.output_dir / settings.mode / run_id, run_id)
    state = TurnContext(settings, source, EvidenceStore(run_id, source.corpus_hash), recorder, Usage(),
                        deadline=started + settings.turn_timeout)
    state.history_message_count = len(session_turn.effective_history) if session_turn else 0
    indexed = isinstance(source, IndexedCorpus)
    config = {**settings.public_config(), "stage": "tool_integration" if indexed else "integration_smoke",
              "retrieval": source.strategy}
    recorder.write("input.json", {"question": question, "effective_history": [], "config": config,
                                  **(session_turn.metadata() if session_turn else {})})
    corpus = {"corpus_hash": source.corpus_hash, "documents": source.snapshot()}
    if indexed:
        corpus["prepared"] = source.retrieval_snapshot.prepared.model_dump(mode="json")
        recorder.write("index-manifest.json", {"index_hash": source.index.index_hash, **source.index.manifest})
        state.knowledge_tools = KnowledgeTools.bind(source, state)
        recorder.event("retrieval_initialized", requested_mode=source.strategy,
                       startup_errors=list(getattr(source.index, "startup_errors", ())))
    recorder.write("corpus.json", corpus)
    if session_turn and session_turn.evidence:
        restored = state.evidence.restore(session_turn.evidence, corpus['documents'])
        packet = {'kind': 'session_evidence', 'sources': [e.model_dump(mode='json') for e in restored]}
        recorder.write('session-evidence.json', packet)
        recorder.event('session_evidence_restored', source_count=len(restored),
                       previous_count=len(session_turn.evidence))
        if restored:
            state.session_evidence_message = json.dumps(packet, ensure_ascii=False)
    recorder.event("input_accepted")
    return state


async def run_turn(
    question: str, settings: Settings, source: KnowledgeSource | IndexedCorpus,
    *, model_factory: ModelFactory | None = None, session: ConversationSession | None = None,
) -> RunResult:
    """Run the framework loop with indexed tools or the explicit legacy smoke source."""
    if settings.mode == "mock" and settings.mock_scenario:
        from knowledge_agent.offline_scenarios import validate_scenario_input
        validate_scenario_input(settings.mock_scenario, question)
        if not isinstance(source, IndexedCorpus):
            raise ValueError("正式 Mock 场景需要实际 BM25 资料与派生块。")
    started = monotonic()
    session_turn = session.prepare(question, settings.max_input_chars) if session else None
    state = create_turn_context(question, settings, source, session_turn=session_turn)
    recorder, run_id = state.recorder, state.recorder.run_id
    if session is not None:
        session.accept(question, run_id, session_turn)
    origin = "model" if settings.mode == "real" else "mock"
    reason = "completed"
    cancelled = False
    try:
        async with asyncio.timeout(max(0, state.deadline - monotonic())):
            async with (model_factory or open_model)(settings) as model:
                recorded = RecordedModel(model, state)
                agent = build_agent(recorded, state)
                messages = session_turn.messages() if session_turn else []
                if state.session_evidence_message:
                    messages.append(ModelRequest(parts=[UserPromptPart(state.session_evidence_message)]))
                result = await agent.run(question, deps=state,
                                         message_history=messages or None,
                                         usage_limits=UsageLimits(request_limit=None))
                history = ([{"role": m.role, "content": m.content} for m in session_turn.effective_history]
                           if session_turn else [])
                for round_number in range(2):
                    check_time(state)
                    state.phase = "answer"
                    # One supplement can require a request, a tool observation, and a final writer call.
                    allow_supplement = (round_number == 0
                                        and result.output.reason not in {"unclear_question", "out_of_scope"}
                                        and settings.max_model_turns - state.usage.model_turns >= 4
                                        and settings.max_tool_calls - state.usage.tool_calls > 1)
                    packet = answer_packet(question, history, state, reason=result.output.reason,
                                           allow_supplement=allow_supplement)
                    recorder.write(f"answer-input-{round_number + 1}.json", packet)
                    recorder.event("answer_started", round=round_number + 1,
                                   source_count=len(packet["sources"]), allow_supplement=allow_supplement)
                    writer = build_answer_agent(recorded, state, allow_supplement=allow_supplement)
                    written = await writer.run(json.dumps(packet, ensure_ascii=False), deps=state,
                                               usage_limits=UsageLimits(request_limit=None))
                    if not isinstance(written.output, EvidenceRequest):
                        answer = state.evidence.materialize(written.output)
                        break
                    state.phase = "research"
                    result = await agent.run(
                        "回答阶段请求补查以下必要证据（不是事实依据）：" + written.output.question,
                        deps=state, message_history=result.all_messages(),
                        usage_limits=UsageLimits(request_limit=None))
                check_time(state)
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
    finally:
        if state.knowledge_tools is not None:
            state.knowledge_tools.search._record_worker_events()
    outcome = RunResult(run_id=run_id, mode=settings.mode, result_origin=origin,
                        stage="tool_integration" if state.knowledge_tools else "integration_smoke",
                        requested_retrieval=source.strategy,
                        termination_reason=reason, result=answer,
                        observed_evidence=state.evidence.snapshot(), usage=state.usage,
                        action_summaries=state.action_summaries, mock_scenario=settings.mock_scenario,
                        session_id=session_turn.session_id if session_turn else None,
                        turn_id=session_turn.turn_id if session_turn else None,
                        previous_run_id=session_turn.previous_run_id if session_turn else None)
    recorder.event("final_result", status=answer.status, termination_reason=reason, result_origin=origin)
    recorder.write("output.json", outcome.model_dump(mode="json"))
    recorder.write("run-summary.json", {"run_id": run_id, "elapsed_seconds": monotonic() - started,
                                       "usage": state.usage.model_dump(), "artifacts_saved": True,
                                       "mode": settings.mode, "stage": outcome.stage,
                                       "session_id": outcome.session_id, "turn_id": outcome.turn_id,
                                       "previous_run_id": outcome.previous_run_id})
    if session is not None:
        session.finish(outcome)
    if cancelled:
        raise TurnCancelled(outcome)
    return outcome
