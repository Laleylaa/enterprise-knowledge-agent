"""Interactive and single-question chat, with explicit session lifecycle."""

import asyncio
import sys
from pathlib import Path

from knowledge_agent.errors import TurnCancelled
from knowledge_agent.presentation import render_result
from knowledge_agent.runtime import run_turn
from knowledge_agent.session import ConversationSession, HistoryInputError, load_history
from knowledge_agent.trace import RunRecorder


def run_chat(settings, source, *, question: str | None = None, history_path: Path | None = None,
             output_format: str = "text") -> int:
    session = ConversationSession()
    recorder = RunRecorder(settings.output_dir / settings.mode / "sessions" / session.session_id, session.session_id)
    run_ids = []
    reason = "error"
    recorder.write("session.json", {"session_id": session.session_id, "config": {**settings.public_config(), "retrieval": source.strategy},
                                     "history_imported": history_path is not None})
    recorder.event("session_started", session_id=session.session_id)

    async def process(text):
        try:
            return await run_turn(text, settings, source, session=session)
        except TurnCancelled as exc:
            return exc.result  # Present saved evidence, then leave the chat; never resume input.

    try:
        if settings.mode == "mock" and settings.mock_scenario:
            from knowledge_agent.offline_scenarios import QUESTIONS
            print(f"离线预设脚本 {settings.mock_scenario}；仅验证流程，不证明模型决策能力。"
                  f"固定输入：{QUESTIONS[settings.mock_scenario]}", file=sys.stderr)
        if history_path is not None:
            try:
                session.history, imported = load_history(history_path, settings.max_input_chars)
            except (HistoryInputError, OSError) as exc:
                recorder.event("input_rejected", reason="invalid_history", error_type=type(exc).__name__)
                raise
            recorder.write("imported-history.json", imported)
            recorder.event("history_imported", source_hash=imported["source_hash"], messages=len(session.history))
        while True:
            if question is None:
                print("请输入问题（/exit 退出）：", end="", file=sys.stderr, flush=True)
                try:
                    text = input()
                except EOFError:
                    reason = "eof"
                    return 0
            else:
                text = question
            if question is None and text.strip() == "/exit":
                reason = "exit_command"
                return 0
            try:
                # Reject before any run directory, model call or user history mutation.
                session.prepare(text, settings.max_input_chars)
                result = asyncio.run(process(text))
            except HistoryInputError as exc:
                recorder.event("input_rejected", reason="empty_or_over_limit", input_chars=len(text))
                print(str(exc), file=sys.stderr)
                if question is not None:
                    reason = "input_rejected"
                    return 2
                continue
            run_ids.append(result.run_id)
            recorder.event("turn_completed", session_id=session.session_id, turn_id=result.turn_id,
                           turn_run_id=result.run_id, status=result.result.status,
                           termination_reason=result.termination_reason)
            recorder.write("history.json", session.export())
            print(result.model_dump_json() if output_format == "json" else render_result(result))
            print(f"运行材料：{settings.output_dir / settings.mode / result.run_id}", file=sys.stderr)
            if result.termination_reason == "user_cancelled":
                reason = "user_cancelled"
                return 130
            if question is not None:
                reason = "question_completed"
                return 1 if result.result.status == "incomplete" else 0
    except KeyboardInterrupt:
        reason = "user_cancelled"
        print("已退出。", file=sys.stderr)
        return 130
    finally:
        # This is an explicit export/audit artifact, never a persistence/resume mechanism.
        try:
            recorder.write("history.json", session.export())
            recorder.event("session_ended", reason=reason, run_ids=run_ids)
        finally:
            session.clear()
