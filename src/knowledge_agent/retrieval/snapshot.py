"""Prepare/load immutable source snapshots and validate cached derived blocks."""

from pathlib import Path

from pydantic import ValidationError

from knowledge_agent.config import Settings
from knowledge_agent.document_loader import load_documents
from knowledge_agent.errors import CorpusError
from knowledge_agent.schemas import Document
from knowledge_agent.retrieval.chunking import chunk_document, sections_for
from knowledge_agent.retrieval.models import PreparedCorpus, digest
from knowledge_agent.retrieval.tokenizer import BgeTokenizer, TOKENIZER_SPEC


def chunker_config(settings: Settings) -> dict:
    return {"algorithm": "markdown-bge-v1", "target_tokens": settings.chunk_target_tokens,
            "max_tokens": settings.chunk_max_tokens, "overlap_tokens": settings.chunk_overlap_tokens}


def identity(documents: list[Document], settings: Settings) -> tuple[str, str]:
    source_hash = digest([d.model_dump(mode="json") for d in documents])
    return source_hash, digest({"source_hash": source_hash, "chunker_config": chunker_config(settings),
                               "tokenizer": TOKENIZER_SPEC, "schema_version": 1})


def blocks_hash(sections, chunks) -> str:
    return digest({"sections": [s.model_dump(mode="json") for s in sections],
                   "chunks": [c.model_dump(mode="json") for c in chunks]})


def prepare_documents(documents: list[Document], settings: Settings) -> PreparedCorpus:
    tokenizer = BgeTokenizer(settings.tokenizer_path)
    sections, chunks = [], []
    for document in documents:
        document_sections, document_chunks = chunk_document(document, tokenizer, settings)
        sections.extend(document_sections)
        chunks.extend(document_chunks)
    source_hash, corpus_hash = identity(documents, settings)
    prepared = PreparedCorpus(source_hash=source_hash, corpus_hash=corpus_hash,
                              chunker_config=chunker_config(settings), tokenizer=TOKENIZER_SPEC,
                              sections=tuple(sections), chunks=tuple(chunks),
                              chunks_hash=blocks_hash(sections, chunks))
    validate_blocks(documents, prepared, settings)
    return prepared


def save_prepared(prepared: PreparedCorpus, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(prepared.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_blocks(documents: list[Document], prepared: PreparedCorpus, settings: Settings) -> None:
    if blocks_hash(prepared.sections, prepared.chunks) != prepared.chunks_hash:
        raise CorpusError("派生块校验和不符，请重新 prepare。")
    expected_sections = tuple(s for d in documents for s in sections_for(d))
    if prepared.sections != expected_sections:
        raise CorpusError("章节定位与原文不一致，请重新 prepare。")
    docs = {d.doc_id: d for d in documents}
    sections = {s.section_id: s for s in prepared.sections}
    if len(sections) != len(prepared.sections):
        raise CorpusError("章节 ID 不唯一。")
    covered = {s.section_id: s.start for s in prepared.sections}
    chunk_ids, counts = set(), {d.doc_id: 0 for d in documents}
    for chunk in prepared.chunks:
        section = sections.get(chunk.section_id)
        document = docs.get(chunk.doc_id)
        if (document is None or section is None or section.doc_id != chunk.doc_id or
                not section.start <= chunk.start < chunk.end <= section.end or
                chunk.text != document.body[chunk.start:chunk.end] or
                chunk.heading_span != section.heading_span or
                chunk.start > covered[chunk.section_id] or chunk.end <= covered[chunk.section_id] or
                not 0 < chunk.token_count <= settings.chunk_max_tokens):
            raise CorpusError("派生块原文、位置、覆盖范围或 token 预算不合法。")
        context = "\n".join(x for x in [document.title, section.heading] if x)
        suffix = "\n" + chunk.text
        if not chunk.index_text.endswith(suffix):
            raise CorpusError("索引输入正文与原文块不一致。")
        prefix = chunk.index_text[:-len(suffix)]
        if (not context.startswith(prefix) or
                (chunk.context_truncated and len(prefix) >= len(context)) or
                (not chunk.context_truncated and prefix != context)):
            raise CorpusError("索引标题上下文不是来源标题的原文前缀。")
        counts[chunk.doc_id] += 1
        if chunk.chunk_id in chunk_ids or chunk.chunk_id != f"{chunk.doc_id}-C{counts[chunk.doc_id]:04d}":
            raise CorpusError("块 ID 重复或顺序不正确。")
        chunk_ids.add(chunk.chunk_id)
        covered[chunk.section_id] = chunk.end
        heading_chars = len(section.heading or "")
        if len(chunk.text) + heading_chars > settings.max_tool_chars:
            raise CorpusError("返回正文预算无法容纳单块及其标题，请调整 max_tool_chars 或重新 prepare。")
    if not prepared.chunks or any(covered[s.section_id] != s.end for s in prepared.sections):
        raise CorpusError("派生块没有完整覆盖原文。")


class RetrievalSnapshot:
    """A loaded snapshot never reads changing source files during a query."""

    def __init__(self, documents: list[Document], prepared: PreparedCorpus, settings: Settings):
        source_hash, corpus_hash = identity(documents, settings)
        if (prepared.source_hash != source_hash or prepared.corpus_hash != corpus_hash or
                prepared.chunker_config != chunker_config(settings) or prepared.tokenizer != TOKENIZER_SPEC):
            raise CorpusError("派生块与原文或配置版本不匹配，请重新 prepare。")
        validate_blocks(documents, prepared, settings)
        self._documents = {d.doc_id: d.model_copy(deep=True) for d in documents}
        self.prepared = prepared.model_copy(deep=True)
        self.corpus_hash = prepared.corpus_hash
        self.chunks = prepared.chunks
        self.sections = {s.section_id: s for s in prepared.sections}

    def get(self, doc_id: str) -> Document | None:
        document = self._documents.get(doc_id)
        return document.model_copy(deep=True) if document else None

    def snapshot(self) -> list[dict]:
        return [d.model_dump(mode="json") for d in self._documents.values()]

    @classmethod
    def load(cls, manifest: Path, prepared_path: Path, settings: Settings) -> "RetrievalSnapshot":
        documents = load_documents(manifest)
        prepared = None
        if prepared_path.is_file():
            try:
                prepared = PreparedCorpus.model_validate_json(prepared_path.read_bytes())
            except (ValueError, ValidationError) as exc:
                raise CorpusError("派生块文件损坏，请重新 prepare。") from exc
        expected_source, expected_corpus = identity(documents, settings)
        stale = prepared is None or (prepared.source_hash, prepared.corpus_hash) != (expected_source, expected_corpus)
        if stale:
            # No automatic network access or substitute character-based chunking.
            if not settings.tokenizer_path.is_file():
                raise CorpusError("派生块缺失或已过期；本地无 tokenizer，请先 download-tokenizer / prepare。")
            prepared = prepare_documents(documents, settings)
            save_prepared(prepared, prepared_path)
        return cls(documents, prepared, settings)
