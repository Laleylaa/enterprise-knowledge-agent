"""Load authoritative Markdown sources through a versioned metadata manifest."""

from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, ValidationError

from knowledge_agent.errors import CorpusError
from knowledge_agent.schemas import Document, NonEmpty, StrictModel


class DocumentMetadata(StrictModel):
    doc_id: NonEmpty
    title: NonEmpty
    version_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_path: NonEmpty


class SourceManifest(StrictModel):
    schema_version: Literal[1]
    documents: list[DocumentMetadata] = Field(min_length=1)


def load_documents(manifest_path: Path) -> list[Document]:
    """Preserve source text exactly; do not chunk, index or infer business rules."""
    try:
        manifest = SourceManifest.model_validate_json(manifest_path.read_bytes())
        root = manifest_path.resolve().parent
        documents = []
        ids: set[str] = set()
        paths: set[Path] = set()
        for metadata in manifest.documents:
            relative = PurePosixPath(metadata.source_path)
            if (relative.is_absolute() or ".." in relative.parts or
                    "\\" in metadata.source_path or relative.suffix != ".md"):
                raise CorpusError("原文路径须为清单目录内的相对 .md 路径，不允许向上跳转。")
            source = (root / relative).resolve()
            if not source.is_relative_to(root):
                raise CorpusError("原文路径不能越过清单所在目录。")
            if metadata.doc_id in ids or source in paths:
                raise CorpusError("资料清单中的文档 ID 和原文路径不能重复。")
            # Decode bytes rather than read_text: preserve CRLF and all source offsets.
            body = source.read_bytes().decode("utf-8")
            documents.append(Document.model_validate({
                **metadata.model_dump(exclude={"source_path"}), "body": body,
            }))
            ids.add(metadata.doc_id)
            paths.add(source)
        return documents
    except (OSError, UnicodeError, ValidationError) as exc:
        raise CorpusError("无法加载知识资料：需要有效的元数据清单和 UTF-8 Markdown 原文。") from exc
