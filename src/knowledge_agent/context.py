"""Explicit per-run dependencies; nothing is kept in module globals."""

from dataclasses import dataclass, field

from knowledge_agent.config import Settings
from knowledge_agent.corpus import KnowledgeSource
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.schemas import Usage
from knowledge_agent.trace import RunRecorder


@dataclass
class TurnContext:
    settings: Settings
    source: KnowledgeSource
    evidence: EvidenceStore
    recorder: RunRecorder
    usage: Usage
    deadline: float
    pending_tools: set[tuple[str, str]] = field(default_factory=set)
    mixed_response: bool = False
    output_retries_used: int = 0
    rejected_output_turn: int | None = None
