import json
import pytest
from tests.support.live import deadline
from tests.support.single_turn import ToolFaultPlan, evaluate_case
pytestmark = [pytest.mark.live, pytest.mark.business]

# Each test covers a distinct assignment acceptance point; no repeated sampling.
def test_clear_answer(cli_run):
    result, records, _ = cli_run('required_clear_answer', '国内差旅报销期限多久？')
    assert evaluate_case('Q01', result, records, ToolFaultPlan())['automatic_pass']

def test_conflicting_documents(cli_run):
    result, records, _ = cli_run('required_conflict', '差旅报销期限多久？', 'F2_conflicting_rules')
    assert evaluate_case('Q02', result, records, ToolFaultPlan())['automatic_pass']

def test_outside_material(cli_run):
    result, _, _ = cli_run('required_missing', '公司育儿假有多少天？', 'F5_leave_and_scope')
    assert result['result']['status'] == 'unresolved'
    assert result['result']['gaps']
    # Review separately: no invented leave entitlement or irrelevant supporting quote.

def test_paraphrased_question(cli_run):
    for variant, question in [('a','国内差旅报销期限多久？'), ('b','国内出差回来最迟多久交报销？')]:
        result, _, _ = cli_run('required_paraphrase_'+variant, question)
        deadline(result, 30)

def test_context_followup(live_chat):
    results = live_chat('required_context', ['国内差旅报销有什么要求？', '期限呢'])
    deadline(results[1], 30)
    # Review both the broad answer's citation coverage and the narrowed follow-up.

def test_tool_failure(cli_run):
    fault = ToolFaultPlan('always')
    result, records, _ = cli_run('required_tool_failure', '国内差旅报销期限多久？', fault=fault)
    assert evaluate_case('Q14a', result, records, fault)['automatic_pass']
