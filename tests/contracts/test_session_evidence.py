"""Cross-turn original sources, invalidation and text-import isolation; no live API."""

import asyncio
import json

import pytest
from pydantic_ai.messages import ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart, UserPromptPart

from knowledge_agent.evidence import EvidenceStore
from knowledge_agent.knowledge_base import IndexedCorpus
from knowledge_agent.runtime import run_turn
from knowledge_agent.session import ConversationSession, load_history
from tests.support.retrieval import ROOT
from tests.support.single_turn import audit_run

pytestmark = pytest.mark.contract


def packet_in(messages, kind):
    for message in messages:
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                try:
                    value = json.loads(part.content)
                except ValueError:
                    continue
                if isinstance(value, dict) and value.get('kind') == kind:
                    return value


async def respond(messages, info):
    packet = packet_in(messages, 'answer_input')
    if packet:
        sources = [s for s in packet['sources'] if '天内提交' in s['text']]
        return ModelResponse(parts=[ToolCallPart('submit_answer', {
            'parts': [{'text': '；'.join(s['text'] for s in sources),
                       'source_ids': [s['source_id'] for s in sources]}],
            'status': 'resolved', 'gaps': [], 'clarification': None,
            'decision_summary': '受控模型仅核对原文交接与引用。',
        })])
    reused = packet_in(messages, 'session_evidence')
    returned = any(isinstance(p, ToolReturnPart) and p.tool_name in {'search_knowledge', 'read_document'}
                   for m in messages for p in m.parts)
    if (reused and reused['sources']) or returned:
        return ModelResponse(parts=[ToolCallPart('finish_research', {
            'reason': 'sufficient', 'decision_summary': '已收到原文。',
        })])
    return ModelResponse(parts=[ToolCallPart('search_knowledge', {
        'query': '国内差旅报销期限', 'purpose': '取得原文',
    }, 'contract-search')])


@pytest.fixture
def session_runner(loop_environment, local_model_factory, archive_run):
    settings, _ = loop_environment
    settings = settings.model_copy(update={'retrieval_mode': 'bm25', 'mock_scenario': None})
    def run(session, fixture='F1_single_rule', *, model_reply=respond):
        with IndexedCorpus.load(ROOT / 'data/fixtures' / fixture / 'manifest.json',
                                ROOT / 'data/prepared' / f'{fixture}.json', settings) as source:
            result = asyncio.run(run_turn('国内差旅报销期限多久？', settings, source,
                                          model_factory=local_model_factory(model_reply), session=session))
        directory = settings.output_dir / result.mode / result.run_id
        archive_run('contracts', 'session_evidence', directory)
        assert result.termination_reason == 'completed', result
        history = json.loads((directory / 'input.json').read_text())['effective_history']
        audit_run(directory, result.model_dump(mode='json'), expected_history=history)
        return result, directory
    return run


def test_reuses_original_sources_without_tools_across_three_turns(session_runner):
    session = ConversationSession()
    first, _ = session_runner(session)
    assert first.usage.tool_calls == 1
    for _ in range(2):
        following, directory = session_runner(session)
        assert following.usage.tool_calls == 0
        assert following.result.citations
        assert all('30 天' in c.quote for c in following.result.citations)
        assert all(e.reused_from in {x.evidence_id for x in first.observed_evidence}
                   and e.delivered_to_model for e in following.observed_evidence)
        assert all(c.evidence_id.startswith(following.run_id + ':') for c in following.result.citations)
        assert (directory / 'session-evidence.json').exists()
        assert len(session.evidence) <= len(first.observed_evidence)


def test_changed_corpus_invalidates_session_sources(session_runner):
    session = ConversationSession()
    first, _ = session_runner(session)
    second, directory = session_runner(session, 'F6_replaced_rule')
    assert second.usage.tool_calls == 1
    assert json.loads((directory / 'session-evidence.json').read_text())['sources'] == []
    assert all(e.reused_from is None for e in second.observed_evidence)
    assert all('20 天' in c.quote and '30 天' not in c.quote for c in second.result.citations)
    assert first.observed_evidence[0].corpus_hash != second.observed_evidence[0].corpus_hash


@pytest.mark.parametrize('boundary', ['clear', 'import'])
def test_clearing_or_importing_text_does_not_reuse_sources(session_runner, tmp_path, boundary):
    session = ConversationSession()
    session_runner(session)
    if boundary == 'clear':
        session.clear()
        assert not session.evidence and not session.history
    else:
        path = tmp_path / 'history.json'
        path.write_text(json.dumps(session.export(), ensure_ascii=False))
        history, _ = load_history(path, 100000)
        session = ConversationSession(history=history)
        assert session.history and not session.evidence
    attempted_stale_finish = False
    correction_observed = False

    async def stale_history_reply(messages, info):
        nonlocal attempted_stale_finish, correction_observed
        if not attempted_stale_finish:
            assert packet_in(messages, 'session_evidence') is None
            attempted_stale_finish = True
            return ModelResponse(parts=[ToolCallPart('finish_research', {
                'reason': 'sufficient', 'decision_summary': '误将历史中的30天答案视为原文。',
            })])
        if not correction_observed:
            feedback = [p for m in messages for p in m.parts
                        if isinstance(p, (RetryPromptPart, ToolReturnPart))]
            assert any(p.tool_name == 'finish_research' and '原文' in str(p.content) for p in feedback)
            correction_observed = True
        return await respond(messages, info)

    result, directory = session_runner(
        session, 'F6_replaced_rule' if boundary == 'import' else 'F1_single_rule',
        model_reply=stale_history_reply if boundary == 'import' else respond,
    )
    assert result.usage.tool_calls == 1
    assert all(e.reused_from is None for e in result.observed_evidence)
    assert not (directory / 'session-evidence.json').exists()
    if boundary == 'import':
        assert attempted_stale_finish and correction_observed
        assert all('20 天' in c.quote and '30 天' not in c.quote for c in result.result.citations)
        events = [json.loads(line) for line in (directory / 'trace.jsonl').read_text().splitlines()]
        failures = [e for e in events if e['event_type'] == 'validation_failed']
        assert len(failures) == 1 and failures[0]['payload']['kind'] == 'research_without_evidence'


def test_unobserved_or_changed_source_cannot_be_restored(reader_factory):
    tool = reader_factory()
    tool.execute({'doc_id': 'D01', 'purpose': '检查复用边界'}, call_id='original-read')
    store = EvidenceStore('new-turn', tool.snapshot.corpus_hash)
    documents = tool.snapshot.snapshot()
    assert not store.restore(tool.evidence.snapshot(), documents)
    tool.evidence.mark_delivered({'original-read'})
    for field, value in [('title', '不同标题'), ('content_hash', 'changed'), ('text', '被修改的原文')]:
        items = [e.model_copy(update={field: value}) for e in tool.evidence.snapshot()]
        assert not store.restore(items, documents)
    assert store.restore(tool.evidence.snapshot(), documents)
    assert not store.sources()  # Restoring is not proof that the model received the sources.
