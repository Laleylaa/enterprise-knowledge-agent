"""Tool functions adapt a knowledge source; they do not decide business outcomes."""

from pydantic_ai import RunContext

from knowledge_agent.context import TurnContext
from knowledge_agent.schemas import Document, NonEmpty

BUSINESS_TOOLS = frozenset({"search_knowledge", "read_document"})


def _result(ctx: RunContext[TurnContext], tool: str, documents: list[Document],
            purpose: str, arguments: dict, *, missing: bool = False) -> dict:
    state = ctx.deps
    call_id = ctx.tool_call_id or f"local-{state.usage.tool_calls}"
    state.recorder.event("tool_started", tool=tool, tool_call_id=call_id,
                         arguments=arguments, purpose=purpose)
    items = []
    for document in documents:
        evidence = state.evidence.add(document, call_id)
        items.append({
            "evidence_id": evidence.evidence_id,
            "doc_id": document.doc_id,
            "title": document.title,
            "version_date": document.version_date.isoformat(),
            "content_hash": evidence.content_hash,
            "section_id": f"{document.doc_id}-ROOT",
            "section_heading": None,
            "heading_span": None,
            "chunk_id": None,
            "source_span": {"start": 0, "end": len(document.body)},
            "text": document.body,
        })
    is_search = tool == "search_knowledge"
    result = {
        "schema_version": 1,
        "tool": tool,
        "tool_call_id": call_id,
        "corpus_hash": state.source.corpus_hash,
        "status": "error" if missing else "ok" if items else "empty",
        "data": {"hits": items if is_search else [], "segments": [] if is_search else items, "locators": []},
        "errors": [{"code": "NOT_FOUND", "message": "该文档不在本次资料快照中。",
                    "retryable": False, "target": {"kind": "doc", "id": arguments["doc_id"]}}] if missing else [],
        "execution": {"strategy": state.source.strategy, "requested_mode": "smoke_fixture" if is_search else None,
                      "effective_branches": [], "next_cursor": None, "has_more": False, "return_limited": False},
    }
    state.recorder.append("tool-results.jsonl", result)
    state.recorder.event("tool_result", tool=tool, tool_call_id=call_id,
                         status=result["status"], doc_ids=[d.doc_id for d in documents])
    return result


async def search_knowledge(ctx: RunContext[TurnContext], query: NonEmpty, purpose: NonEmpty) -> dict:
    """取得冒烟资料候选。仅返回本次小型合成资料全集；尚未实现关键词或向量排序。

    Args:
        query: 要查找的制度问题；冒烟资料源不会按此参数筛选。
        purpose: 简短行动目的，不要提供内部思维过程。
    """
    return _result(ctx, "search_knowledge", ctx.deps.source.candidates(), purpose, {"query": query})


async def read_document(ctx: RunContext[TurnContext], doc_id: NonEmpty, purpose: NonEmpty) -> dict:
    """根据文档 ID 读取合成资料原文。

    Args:
        doc_id: 原文文档 ID。
        purpose: 简短行动目的，不要提供内部思维过程。
    """
    document = ctx.deps.source.get(doc_id)
    return _result(ctx, "read_document", [document] if document else [], purpose,
                   {"doc_id": doc_id}, missing=document is None)
