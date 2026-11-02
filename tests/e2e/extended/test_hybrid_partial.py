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
        ('先按“草稿保存时间”检索一条片段，再核实海外差旅是否也必须在行程结束后30天内提交？',
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
        first_text = '\n'.join(h['text'] for h in searches[0]['data']['hits'])
        assert '30 天内提交' in first_text and '仅适用于国内差旅' not in first_text
        # The fixture's section contains the condition omitted from the first hit.
        # Accept any subsequent evidence-gathering action that actually obtains it.
        assert any('仅适用于国内差旅' in e['text'] and e['delivered_to_model']
                   for e in result['observed_evidence'])
        answer = result['result']
        assert answer['status'] in {'resolved', 'unresolved', 'needs_info'}
        assert any('仅适用于国内差旅' in c['quote'] for c in answer['citations'])
        # Review separately: do not assign the domestic 30-day rule to overseas travel.
