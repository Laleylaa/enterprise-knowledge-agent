"""Typed, immutable derived objects. Markdown remains the only source text."""

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from knowledge_agent.schemas import StrictModel


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


class FrozenModel(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Span(FrozenModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def forward(self):
        if self.end <= self.start:
            raise ValueError("source span must advance")
        return self


class Section(FrozenModel):
    doc_id: str
    section_id: str
    start: int
    end: int
    heading: str | None
    heading_span: Span | None


class Chunk(FrozenModel):
    doc_id: str
    section_id: str
    chunk_id: str
    start: int
    end: int
    heading_span: Span | None
    text: str
    index_text: str
    token_count: int
    context_truncated: bool


class PreparedCorpus(FrozenModel):
    schema_version: Literal[1] = 1
    source_hash: str
    corpus_hash: str
    chunker_config: dict
    tokenizer: dict
    sections: tuple[Section, ...]
    chunks: tuple[Chunk, ...]
    chunks_hash: str
