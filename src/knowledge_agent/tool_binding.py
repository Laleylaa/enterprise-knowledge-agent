"""Standard PydanticAI function-tool bindings; no custom FC parsing or routing."""

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from knowledge_agent.context import TurnContext
from knowledge_agent.knowledge_base import IndexedCorpus
from knowledge_agent.reading.tool import ReadRequest, ReadTool
from knowledge_agent.retrieval.tool import SearchRequest, SearchTool


@dataclass
class KnowledgeTools:
    search: SearchTool
    reader: ReadTool

    @classmethod
    def bind(cls, source: IndexedCorpus, state: TurnContext) -> "KnowledgeTools":
        # Both tools share this turn's identity, evidence and recorder; cursors stay per turn.
        return cls(SearchTool(source.index, state.settings, state.evidence, state.recorder, standalone=False),
                   ReadTool(source.retrieval_snapshot, state.settings, state.evidence, state.recorder, standalone=False))


async def search_knowledge(ctx: RunContext[TurnContext], request: SearchRequest) -> dict:
    """Search the prepared knowledge base using the public SearchRequest contract."""
    assert ctx.deps.knowledge_tools is not None and ctx.tool_call_id is not None
    return ctx.deps.knowledge_tools.search.execute(request.model_dump(), call_id=ctx.tool_call_id)


async def read_document(ctx: RunContext[TurnContext], request: ReadRequest) -> dict:
    """Read a source document, section or chunk using the public ReadRequest contract."""
    assert ctx.deps.knowledge_tools is not None and ctx.tool_call_id is not None
    return ctx.deps.knowledge_tools.reader.execute(request.model_dump(), call_id=ctx.tool_call_id)


def register_knowledge_tools(agent: Agent) -> None:
    # PydanticAI unwraps the single Pydantic argument into top-level JSON fields.
    # The framework validates FC arguments and dispatches by name. No JSON parser,
    # hand-maintained parameter schema, or Python tool-selection branch is used here.
    agent.tool(search_knowledge, name=SearchTool.name, description=SearchTool.description, sequential=True)
    agent.tool(read_document, name=ReadTool.name, description=ReadTool.description, sequential=True)
