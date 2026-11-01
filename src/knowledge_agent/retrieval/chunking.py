"""Source-preserving Markdown sections and BGE-token-bounded chunks."""

import re

from knowledge_agent.config import Settings
from knowledge_agent.errors import CorpusError
from knowledge_agent.schemas import Document
from knowledge_agent.retrieval.models import Chunk, Section, Span
from knowledge_agent.retrieval.tokenizer import BgeTokenizer

HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*(?:\r?\n)?$")


def sections_for(document: Document) -> list[Section]:
    """ATX headings outside fenced code; sections partition the exact source."""
    headings, offset, fence = [], 0, None
    for line in document.body.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif fence is None and (match := HEADING.match(line)):
            headings.append((offset, match.group(1), Span(start=offset + match.start(1),
                                                         end=offset + match.end(1))))
        offset += len(line)
    boundaries = []
    if not headings or headings[0][0] > 0:
        boundaries.append((0, None, None, f"{document.doc_id}-ROOT"))
    boundaries.extend((start, title, span, f"{document.doc_id}-S{i:04d}")
                      for i, (start, title, span) in enumerate(headings, 1))
    return [Section(doc_id=document.doc_id, section_id=identity, start=start,
                    end=boundaries[i + 1][0] if i + 1 < len(boundaries) else len(document.body),
                    heading=title, heading_span=span)
            for i, (start, title, span, identity) in enumerate(boundaries)]


def chunk_document(document: Document, tokenizer: BgeTokenizer, settings: Settings) -> tuple[list[Section], list[Chunk]]:
    sections, chunks = sections_for(document), []
    target, hard = settings.chunk_target_tokens, settings.chunk_max_tokens
    for section in sections:
        original_context = "\n".join(x for x in [document.title, section.heading] if x)
        context_offsets = tokenizer.offsets(original_context)
        context_limit = min(64, target // 4)
        truncated = len(context_offsets) > context_limit
        context = original_context[:context_offsets[context_limit - 1][1]] if truncated else original_context
        prefix = context + "\n"
        start, covered = section.start, section.start
        while start < section.end:
            tail = document.body[start:section.end]
            if tokenizer.count(prefix + tail) <= target:
                end = section.end
            else:
                offsets = tokenizer.offsets(tail)
                allowance = max(1, target - tokenizer.count(prefix) - 2)
                if not offsets:
                    raise CorpusError("无法对原文建立前进的 token 窗口。")
                end = start + offsets[min(allowance, len(offsets)) - 1][1]
                # Re-encode the actual combined input; token counts need not be additive.
                while end > start and tokenizer.count(prefix + document.body[start:end]) > hard:
                    end -= 1
                window = document.body[start:end]
                paragraphs = list(re.finditer(r"\r?\n[ \t]*\r?\n", window))
                sentences = list(re.finditer(r"[。！？!?；;](?:[ \t]*\r?\n)?", window))
                boundaries = paragraphs or sentences
                if boundaries and start + boundaries[-1].end() > covered:
                    end = start + boundaries[-1].end()
            if end <= start:
                raise CorpusError("分块无法在 token 预算内前进。")
            text = document.body[start:end]
            index_text = prefix + text
            count = tokenizer.count(index_text)
            if count > hard:
                raise CorpusError("分块超过 token 硬上限，未截断原文。")
            chunks.append(Chunk(doc_id=document.doc_id, section_id=section.section_id,
                                chunk_id=f"{document.doc_id}-C{len(chunks) + 1:04d}", start=start, end=end,
                                heading_span=section.heading_span, text=text, index_text=index_text,
                                token_count=count, context_truncated=truncated))
            covered = end
            if end == section.end:
                break
            # Prefer a complete final sentence for overlap, otherwise use tokenizer offsets.
            offsets = tokenizer.offsets(text)
            overlap = settings.chunk_overlap_tokens
            next_start = end
            if overlap and len(offsets) > overlap:
                candidate = start + offsets[-overlap][0]
                sentence_ends = [start + m.end() for m in re.finditer(r"[。！？!?；;]", text)
                                 if candidate <= start + m.end() < end]
                next_start = sentence_ends[0] if sentence_ends else candidate
            start = max(start + 1, next_start)
    return sections, chunks
