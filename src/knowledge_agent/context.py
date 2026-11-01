"""Explicit per-run dependencies; nothing is kept in module globals."""

from dataclasses import dataclass

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
    mixed_response: bool = False
