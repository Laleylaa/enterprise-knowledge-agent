"""Live decisions after an explicitly injected vector-branch timeout.

BM25 and source reading run normally. The model sees only the actual partial
tool response; semantic conclusions are reviewed separately from these checks.
"""

import pytest

from knowledge_agent.retrieval.failures import RetrievalFailure
from tests.support.live import deadline
from tests.support.single_turn import ToolFaultPlan

pytestmark = [pytest.mark.live, pytest.mark.business]


class VectorTimeoutPlan(ToolFaultPlan):
    def __init__(self):
        super().__init__('always', targets=('search_knowledge',))

    def _inject(self, tool, call_id, patch):
        self.attempts += 1
        vector = getattr(tool.index, 'backends', {}).get('vector')
        assert vector is not None, 'This scenario requires an initialized hybrid vector branch'

        async def fail(*args, **kwargs):
            record = {'tool': tool.name, 'tool_call_id': call_id, 'branch': 'vector',
                      'injection': 'test_embedding_timeout', 'execution_number': self.attempts}
            self.injected.append(record)
            tool.recorder.event('test_fault_injected', origin='test', **record)
            raise RetrievalFailure('EMBEDDING_TIMEOUT', '本地 embedding 超时，未取得向量候选。', retryable=True)

        patch.setattr(vector, 'arank', fail)


@pytest.mark.parametrize('case', ['sufficient', 'section_context'])
def test_hybrid_partial_evidence_decision(cli_run, evaluation_settings, case):
    if evaluation_settings is not None and evaluation_settings.selected_retrieval != 'hybrid':
        pytest.skip('Hybrid-specific scenario: use evaluate --mode real --retrieval hybrid --run-live')
    fault = VectorTimeoutPlan()
    question, fixture = (
        ('国内差旅报销期限多久？', 'F1_single_rule') if case == 'sufficient' else
        ('我是海外差旅，看到报销说明里写行程结束后30天内提交，这条也适用于我吗？',
         'R1_section_context')
    )
    result, records, _ = cli_run('hybrid_partial_' + case, question, fixture, fault=fault)
    searches = [r for r in records['returns'] if r['tool'] == 'search_knowledge']
    assert fault.injected and searches
    assert all(r['status'] == 'partial' and r['execution']['effective_branches'] == ['bm25']
               and any(e['code'] == 'EMBEDDING_TIMEOUT' for e in r['errors']) for r in searches)
    if case == 'sufficient':
        deadline(result, 30)
        # No mandatory reread or restoration of the vector branch.
    else:
        # Natural business input does not prescribe the query or first-hit contents.
        scope_sources = [e for e in result['observed_evidence']
                         if '仅适用于国内差旅' in e['text'] and e['delivered_to_model']]
        assert scope_sources
        answer = result['result']
        assert result['result_origin'] == 'model' and result['termination_reason'] == 'completed'
        assert answer['status'] == 'resolved'
        assert answer['gaps'] == [] and answer['clarification'] is None
        assert any('仅适用于国内差旅' in c['quote'] for c in answer['citations'])
        # Permit any necessary search/read before the scope arrives, but no further
        # business calls once the model observes the explicit applicability rule.
        scope_calls = {e['tool_call_id'] for e in scope_sources}
        observed_turns = [r['model_turn'] for r in records['requests'] if any(
            p.get('part_kind') == 'tool-return' and p.get('tool_call_id') in scope_calls
            for m in r['messages'] for p in m['parts'])]
        assert observed_turns
        assert not any(e['event_type'] == 'tool_requested'
                       and e['payload']['model_turn'] >= min(observed_turns)
                       for e in records['events'])
        assert not any(e['event_type'] == 'evidence_requested' for e in records['events'])
        assert any(e['event_type'] == 'research_complete'
                   and e['payload']['result']['reason'] == 'sufficient'
                   for e in records['events'])
        # Review separately: do not assign the domestic 30-day rule to overseas travel.
