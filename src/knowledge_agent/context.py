"""Explicit per-run dependencies; nothing is kept in module globals."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from knowledge_agent.config import Settings
from knowledge_agent.corpus import KnowledgeSource
from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.schemas import Usage
from knowledge_agent.trace import RunRecorder

if TYPE_CHECKING:
    from knowledge_agent.knowledge_base import IndexedCorpus
    from knowledge_agent.tool_binding import KnowledgeTools


@dataclass
class TurnContext:
    settings: Settings
    source: "KnowledgeSource | IndexedCorpus"
    evidence: EvidenceStore
    recorder: RunRecorder
    usage: Usage
    deadline: float
    pending_tools: set[tuple[str, str]] = field(default_factory=set)
    mixed_response: bool = False
    output_retries_used: int = 0
    rejected_output_turn: int | None = None
    knowledge_tools: "KnowledgeTools | None" = None
    action_summaries: list[dict] = field(default_factory=list)
    history_message_count: int = 0
    session_evidence_message: str | None = None
    tool_deadline: float | None = None
    phase: str = "research"
    tool_observations: list[dict] = field(default_factory=list)
