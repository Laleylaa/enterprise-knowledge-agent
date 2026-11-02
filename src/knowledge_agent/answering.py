"""Program-owned raw-evidence handoff; no collector summaries become source facts."""

from knowledge_agent.context import TurnContext


def answer_packet(question: str, history: list[dict], state: TurnContext, *, reason: str,
                  allow_supplement: bool) -> dict:
    observations = []
    for result in state.tool_observations:
        data = result.get("data", {}) or {}
        observations.append({
            "tool": result.get("tool"), "tool_call_id": result.get("tool_call_id"),
            "status": result.get("status"), "errors": result.get("errors", []),
            "execution": result.get("execution", {}),
            "returned_items": len(data.get("hits", data.get("segments", []))),
        })
    return {
        "kind": "answer_input", "question": question, "history": history,
        "sources": state.evidence.sources(), "tool_observations": observations,
        "research_stop_reason": reason,
        "budget": {
            "remaining_model_turns": state.settings.max_model_turns - state.usage.model_turns,
            "remaining_tool_calls": state.settings.max_tool_calls - state.usage.tool_calls,
            "allow_supplement": allow_supplement,
        },
    }
