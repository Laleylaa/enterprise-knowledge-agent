"""Stable exports; each stage owns its identity, rules and output contract."""

from knowledge_agent.answer_prompt import ANSWER_INSTRUCTIONS
from knowledge_agent.research_prompt import INSTRUCTIONS, conversation_context

__all__ = ["INSTRUCTIONS", "ANSWER_INSTRUCTIONS", "conversation_context"]
