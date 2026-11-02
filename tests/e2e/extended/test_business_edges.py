import json
import pytest
from tests.support.live import deadline
from tests.support.single_turn import ToolFaultPlan, evaluate_case
pytestmark = [pytest.mark.live, pytest.mark.business]
def test_Q02_newer_date_does_not_resolve_conflict(cli_run):
    result,records,_=cli_run('extended_conflict_newer','差旅报销期限多久？','F2_newer_D02')
    report=evaluate_case('Q02',result,records,ToolFaultPlan())
    assert report['automatic_pass'],report


def test_Q11_unknown_referent(cli_run):
    result,_,_=cli_run('extended_unknown_referent','这个能报销吗？','F5_leave_and_scope')
    assert result['result']['status']=='needs_info' and result['result']['clarification']


def test_Q13_partial_answer_preserves_missing_item(cli_run):
    result,_,_=cli_run('extended_partial_answer','国内差旅报销期限多久，需要哪些凭证？')
    a=result['result'];assert a['status'] in {'unresolved','needs_info'}
    assert any(c['doc_id']=='D01' and '30 天' in c['quote'] for c in a['citations'])
    assert a['gaps']  # Review meaning: receipt/material requirements remain unanswered.


def test_Q18_replacement_ignores_old_answer(cli_run):
    import_old = True
    case='Q18b' if import_old else 'Q18a'
    before,_,first=cli_run(case+'_before','国内差旅报销期限多久？');deadline(before,30)
    history=cli_run.root/'real/sessions'/before['session_id']/'history.json' if import_old else None
    after,_,second=cli_run(case+'_after','国内差旅报销期限多久？','F6_replaced_rule',history=history)
    deadline(after,20)
    # Mentioning the old answer as a comparison is allowed; endorsement is reviewed semantically.
    first_c=json.loads((first/'corpus.json').read_text());second_c=json.loads((second/'corpus.json').read_text())
    assert first_c['corpus_hash']!=second_c['corpus_hash']
    assert {e['content_hash'] for e in before['observed_evidence']}.isdisjoint({e['content_hash'] for e in after['observed_evidence']})
    assert all('30 天' not in c['quote'] for c in after['result']['citations'])
    effective=json.loads((second/'input.json').read_text())['effective_history']
    assert bool(effective)==import_old
    if import_old:assert any('30' in h['content'] for h in effective)
    for path,other in [(first,after),(second,before)]:
        (path/'replacement-link.json').write_text(json.dumps({'other_run_id':other['run_id'],'imported_old_history':import_old}))


def test_read_backend_failure_can_be_handled(cli_run):
    fault=ToolFaultPlan('always',targets=('read_document',))
    result,records,_=cli_run('extended_read_failure',
        '请读取 D01 原文，核实国内差旅报销期限。',fault=fault)
    assert fault.injected,'必须实际执行读取故障，不将未触发场景计为通过'
    assert any(r['tool']=='read_document' and any(e['code']=='READ_FAILED' for e in r['errors']) for r in records['returns'])
    if result['result']['status']=='resolved':deadline(result,30)
    else:
        # Search may have provided valid partial evidence while required reading failed.
        # audit_run already checks every citation; incomplete does not imply zero citations.
        assert result['result']['status']=='incomplete'
        assert result['result']['gaps']

def test_scope_lookup_does_not_expand_deadline_answer(cli_run):
    result, records, _ = cli_run('extended_scope',
        '我是国内差旅，预置 D03 据说说明了 D01 与 D02 的适用范围，请查证报销期限。',
        'F4_scope_evidence')
    deadline(result, 30)
    # The scope must be supported by delivered original text, from either tool.
    assert any(c['doc_id'] == 'D03' and 'D01 适用于国内差旅' in c['quote']
               for c in result['result']['citations'])


def test_notification_without_channel_is_not_classified(live_chat):
    results = live_chat('extended_notification', [
        '差旅报销期限多久？',
        '人事刚通知以 15 天为准，我没有更多可核实的线索',
    ], 'F2_conflicting_rules')
    assert results[0]['result']['status'] == 'needs_info'
    answer = results[1]['result']
    assert answer['status'] == 'unresolved' and answer['clarification'] is None
    assert {c['doc_id'] for c in answer['citations']} == {'D01', 'D02'}
    assert all(str(n) in '\n'.join(c['quote'] for c in answer['citations']) for n in (30, 15))


def test_explicit_status_question_is_still_answered(cli_run):
    result, _, _ = cli_run('extended_status', '国内差旅报销申请显示“已提交”，是否代表审核通过？')
    answer = result['result']
    assert answer['status'] == 'resolved'
    assert any('不代表审核通过' in c['quote'] for c in answer['citations'])


def test_recover_after_tool_error(cli_run):
    fault = ToolFaultPlan('first')
    result, records, _ = cli_run('extended_recovery', '国内差旅报销期限多久？', fault=fault)
    assert evaluate_case('Q14b', result, records, fault)['automatic_pass']

def test_user_corrects_scope(live_chat):
    results = live_chat('extended_scope_correction', ['国内差旅报销期限多久？', '更正一下，我是海外差旅，期限多久？'], 'F5_leave_and_scope')
    deadline(results[0], 30)
    deadline(results[1], 15, 'D02')
