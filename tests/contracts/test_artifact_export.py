"""Submission projection must preserve business results and failed decisions."""

import json
from pathlib import Path

import pytest

from knowledge_agent.artifact_export import export_run
from knowledge_agent.submission import publish


def put(path, value, jsonl=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in value) if jsonl else
                     json.dumps(value, ensure_ascii=False)))


@pytest.fixture
def raw_run(tmp_path):
    root = tmp_path / 'raw' / 'turn2'
    document = {'doc_id': 'D01', 'title': '制度', 'version_date': '2026-01-01', 'body': '提交期限30天。'}
    put(root / 'corpus.json', {'corpus_hash': 'corpus', 'documents': [document], 'prepared': {'debug': 'omit'}})
    put(root / 'input.json', {'question': '期限呢？', 'effective_history': [{'role': 'user', 'content': '差旅报销'}],
                              'config': {'mode': 'real', 'model_name': 'local-test', 'max_tool_calls': 2}})
    put(root / 'output.json', {'run_id': 'turn2', 'mode': 'real', 'result_origin': 'model',
                               'termination_reason': 'completed', 'usage': {'tool_calls': 1},
                               'result': {'answer': '提交期限30天。', 'status': 'resolved', 'gaps': [],
                                          'clarification': None, 'citations': [{'doc_id': 'D01',
                                          'evidence_id': 'turn2:E1', 'quote': document['body']}]},
                               'observed_evidence': [{'evidence_id': 'turn2:E1', 'doc_id': 'D01',
                                          'tool_call_id': 'previous-tool', 'content_hash': 'hash',
                                          'text': document['body'], 'start': 0, 'end': len(document['body']),
                                          'delivered_to_model': True, 'reused_from': 'turn1:E1'}]})
    call = {'tool_name': 'read_document', 'tool_call_id': 'read-failed',
            'args': '{"doc_id":"D01","purpose":"查证适用范围"}', 'part_kind': 'tool-call'}
    events = [
        ('model_response', {'messages': [{'parts': [call]}]}),
        ('tool_requested', {'tool': 'read_document', 'tool_call_id': 'read-failed', 'arguments': call['args']}),
        ('tool_result', {'tool': 'read_document', 'tool_call_id': 'read-failed', 'status': 'error'}),
        ('model_request_failed', {'retryable': True, 'error_type': 'TimeoutError'}),
        ('model_request_retry', {'model_turn': 2}),
        ('evidence_requested', {'request': {'question': '适用范围'}}),
        ('budget_blocked', {'reason': 'tool_call_limit'}),
        ('validation_failed', {'kind': 'citation_or_status', 'reason': 'unknown source'}),
        ('final_result', {'status': 'resolved'}),
    ]
    put(root / 'trace.jsonl', [{'sequence': i, 'event_type': k, 'payload': v, 'origin': 'test'}
                              for i, (k, v) in enumerate(events, 1)], jsonl=True)
    put(root / 'tool-results.jsonl', [{'tool': 'read_document', 'tool_call_id': 'read-failed',
                                      'status': 'error', 'data': {}, 'errors': [{'code': 'READ_FAILED'}]}], jsonl=True)
    put(root / 'model-inputs.jsonl', [{'instructions': 'repeated diagnostic prompt'}], jsonl=True)
    return root


def test_export_preserves_output_provenance_failures_and_shared_corpus(raw_run, tmp_path):
    dest = tmp_path / 'compact'
    export_run(raw_run, dest, 'notification')
    export_run(raw_run, dest, 'second_case')
    assert len(list(dest.rglob('*.json'))) == 5  # Two input/output pairs, one shared corpus.
    assert len(list(dest.rglob('*.jsonl'))) == 2
    out = json.loads((dest / 'outputs/notification/turn2/output.json').read_text())
    raw = json.loads((raw_run / 'output.json').read_text())
    assert out['result'] == raw['result'] and out['usage'] == raw['usage']
    trace = [json.loads(x) for x in (dest / 'traces/notification/turn2/trace.jsonl').read_text().splitlines()]
    assert trace[0]['items'][0]['reused_from'] == 'turn1:E1'
    assert trace[0]['items'][0]['spans'] == [{'start': 0, 'end': len('提交期限30天。')}]
    assert trace[1]['actions'][0]['args'] == {'doc_id': 'D01', 'purpose': '查证适用范围'}
    assert [e['sequence'] for e in trace[1:]] == list(range(1, 10))
    assert trace[3]['data']['errors'] == [{'code': 'READ_FAILED'}]
    assert not list(dest.rglob('model-inputs.jsonl'))
    assert (raw_run / 'model-inputs.jsonl').exists()
    # Re-exporting the same run is deterministic; different contents cannot overwrite it.
    original = (dest / 'outputs/notification/turn2/output.json').read_bytes()
    export_run(raw_run, dest, 'notification')
    assert (dest / 'outputs/notification/turn2/output.json').read_bytes() == original
    put(raw_run / 'output.json', {**raw, 'result': {**raw['result'], 'answer': 'changed'}})
    with pytest.raises(FileExistsError):
        export_run(raw_run, dest, 'notification')


def test_publish_preserves_failed_test_counts_and_resolvable_sources(raw_run, tmp_path):
    source, output = tmp_path / 'batch', tmp_path / 'submission'
    export_run(raw_run, source / 'offline/e2e', 'notification')
    (source / 'offline-results.xml').write_text('<testsuites><testsuite tests="2" failures="1" errors="0" skipped="0"><testcase name="pass"/><testcase name="fail"><failure>actual failure</failure></testcase></testsuite></testsuites>')
    summary = publish(source, output)
    assert summary['total'] == 2 and summary['passed'] == summary['failed'] == 1
    assert summary['semantic_review'] == 'not_automatically_assessed'
    inp = output / 'cases/notification/turn2/input.json'
    corpus = (inp.parent / json.loads(inp.read_text())['corpus']).resolve()
    assert corpus.is_relative_to(output) and corpus.is_file()
    assert json.loads(corpus.read_text())['documents'][0]['body'] == '提交期限30天。'
    assert len(list(output.rglob('*.*'))) == 7  # Three run files, corpus and three batch files.
    with pytest.raises(ValueError):
        publish(source, output)
