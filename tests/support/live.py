"""Real CLI fixtures. Only fault injection is scripted; decisions use the provider."""
import hashlib
import json
import os
from pathlib import Path
import pytest
from knowledge_agent.agent import INSTRUCTIONS
from knowledge_agent.cli import main
from knowledge_agent.config import load_settings
from tests.support.evaluation import apply_evaluation
from tests.support.single_turn import ToolFaultPlan, audit_run, SEMANTIC_REVIEW_CHECKS
ROOT = Path(__file__).resolve().parents[2]
@pytest.fixture
def cli_run(monkeypatch,tmp_path,capsys,archive_run,request,evaluation_settings):
    credentials=evaluation_settings or load_settings()
    if not credentials.has_api_key:pytest.fail('--run-live requires actual provider credentials')
    for key in tuple(os.environ):
        if key.startswith('KA_') or key=='DEEPSEEK_API_KEY':monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DEEPSEEK_API_KEY',credentials.deepseek_api_key.get_secret_value())
    monkeypatch.setenv('KA_MODEL_NAME',credentials.model_name)
    monkeypatch.setenv('KA_BASE_URL',credentials.base_url)
    monkeypatch.setenv('KA_RETRIEVAL_CACHE_DIR',str(tmp_path/'cache'))
    retrieval = apply_evaluation(monkeypatch, evaluation_settings)
    root=tmp_path/'runs';created=[]
    def execute(case,question,fixture='F1_single_rule',history=None,fault=None):
        fault=fault or ToolFaultPlan()
        existing=set((root/'real').glob('*/output.json'))
        sessions=set((root/'real/sessions').glob('*'))
        args=['chat','--mode','real','--format','json','--question',question,
              '--corpus',str(ROOT/'data/fixtures'/fixture/'manifest.json'),
              '--prepared',str(ROOT/'data/prepared'/f'{fixture}.json'),'--output-dir',str(root)]
        if history:args.extend(['--history',str(history)])
        try:
            with monkeypatch.context() as patch:
                fault.install(patch)
                code=main(args)
        finally:
            for p in set((root/'real').glob('*/output.json'))-existing:
                (p.parent/'run.json').write_text(json.dumps({'scope':'business_cli', 'retrieval':retrieval,'live_model':True,
                    'case_id':case,'model_origin':'live_provider','semantic_review':'pending_separate_review',
                    'agent_source_sha256':hashlib.sha256((ROOT/'src/knowledge_agent/agent.py').read_bytes()).hexdigest()}))
                (p.parent/'fault-injection.json').write_text(json.dumps(fault.snapshot(),ensure_ascii=False,indent=2))
                archive_run('e2e',case,p.parent);created.append((case,p.parent))
            for p in set((root/'real/sessions').glob('*'))-sessions:
                archive_run('e2e',case+'_session',p)
        captured=capsys.readouterr();assert captured.out.strip(),captured.err
        result=json.loads(captured.out);directory=root/'real'/result['run_id']
        inp=json.loads((directory/'input.json').read_text())
        records=audit_run(directory,result,expected_history=inp['effective_history'],expected_retrieval=retrieval)
        assert code==(1 if result['result']['status']=='incomplete' else 0)
        assert result['mode']=='real' and result['mock_scenario'] is None
        assert not any(e['event_type']=='offline_fault_injected' for e in records['events'])
        return result,records,directory
    execute.root=root;execute.tmp=tmp_path
    yield execute
    report=getattr(request.node,'chat_call_report',None)
    for case,path in created:
        (path/'business-evaluation.json').write_text(json.dumps({'case_id':case,'live_model':True,
            'automated_test_outcome':report.outcome if report else 'unknown','test_id':request.node.nodeid,
            'semantic_review':'pending_separate_review',
            'automated_scope':'structure_evidence_execution',
            'required_semantic_checks':SEMANTIC_REVIEW_CHECKS},indent=2))


def deadline(result,days,doc='D01'):
    # Check cited source facts; answer wording and entailment require separate review.
    a=result['result'];assert result['termination_reason']=='completed' and result['result_origin']=='model'
    assert a['status']=='resolved'
    assert any(c['doc_id']==doc and f'{days} 天' in c['quote'] and '行程结束' in c['quote'] for c in a['citations'])

@pytest.fixture
def live_chat(monkeypatch,tmp_path,capsys,archive_run,request,evaluation_settings):
    credentials=evaluation_settings or load_settings()
    if not credentials.has_api_key:pytest.fail('--run-live requires local model credentials')
    for key in tuple(os.environ):
        if key.startswith('KA_') or key=='DEEPSEEK_API_KEY':monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DEEPSEEK_API_KEY',credentials.deepseek_api_key.get_secret_value())
    monkeypatch.setenv('KA_MODEL_NAME',credentials.model_name)
    monkeypatch.setenv('KA_BASE_URL',credentials.base_url)
    monkeypatch.setenv('KA_RETRIEVAL_CACHE_DIR',str(tmp_path/'cache'))
    retrieval = apply_evaluation(monkeypatch, evaluation_settings)
    root=tmp_path/'runs'
    created=[]
    def execute(case,questions,fixture='F1_single_rule',history=None):
        sequence=iter([*questions,'/exit'])
        monkeypatch.setattr('builtins.input',lambda:next(sequence))
        args=['chat','--mode','real','--format','json','--corpus',str(ROOT/'data/fixtures'/fixture/'manifest.json'),
              '--prepared',str(ROOT/'data/prepared'/f'{fixture}.json'),'--output-dir',str(root)]
        if history is not None:args.extend(['--history',str(history)])
        existing=set((root/'real').glob('*/output.json'))
        existing_sessions=set((root/'real/sessions').glob('*'))
        try:
            code=main(args)
        finally:
            for p in set((root/'real').glob('*/output.json'))-existing:
                p.parent.joinpath('run.json').write_text(json.dumps({'scope':'chat_cli_e2e','live_model':True,
                    'model_origin':'live_provider','case_id':case,'semantic_review':'pending_separate_review',
                    'prompt_sha256':hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
                    'agent_source_sha256':hashlib.sha256((ROOT/'src/knowledge_agent/agent.py').read_bytes()).hexdigest()}))
                archive_run('e2e',case,p.parent);created.append((case,p.parent))
            for p in set((root/'real/sessions').glob('*'))-existing_sessions:
                archive_run('e2e',case+'_session',p)
        captured=capsys.readouterr()
        assert code==0,captured.err
        results=[json.loads(line) for line in captured.out.splitlines()]
        assert len(results)==len(questions)
        for i,value in enumerate(results):
            assert value['requested_retrieval']==retrieval
            assert value['result_origin']=='model' and value['termination_reason']=='completed',value
            assert value['turn_id']==i+1
            assert value['previous_run_id']==(results[i-1]['run_id'] if i else None)
            assert value['session_id']==results[0]['session_id']
            path=root/'real'/value['run_id']
            inp=json.loads((path/'input.json').read_text())
            audit_run(path,value,expected_history=inp['effective_history'],expected_retrieval=retrieval)
            assert inp['question']==questions[i]
            # Compare actual first model request with the saved complete conversation snapshot.
            first=json.loads((path/'model-inputs.jsonl').read_text().splitlines()[0])
            text=[p['content'] for m in first['messages'] for p in m['parts'] if p['part_kind'] in {'user-prompt','text'}]
            expected_text=[m['content'] for m in inp['effective_history']]
            reused_path=path/'session-evidence.json'
            if reused_path.exists():
                reused=json.loads(reused_path.read_text())
                if reused['sources']:
                    expected_text.append(json.dumps(reused,ensure_ascii=False))
                    previous={e['reused_from'] or e['evidence_id']:e
                              for e in results[i-1]['observed_evidence'] if e['delivered_to_model']}
                    for item in reused['sources']:
                        original=previous[item['reused_from']]
                        for key in ('corpus_hash','doc_id','content_hash','text','source_spans','tool_call_id'):
                            assert item[key]==original[key]
            assert text==expected_text+[questions[i]]
            assert not any(p['part_kind'] in {'tool-return','tool-call','retry-prompt'} for m in first['messages'] for p in m['parts'])
            assert all(c['evidence_id'].startswith(value['run_id']+':') for c in value['result']['citations'])
        return results
    execute.root=root
    execute.tmp=tmp_path
    yield execute
    # Record assertion outcome separately from semantic review, including all completed turns.
    outcome=getattr(request.node,'chat_call_report',None)
    for case,path in created:
        (path/'chat-evaluation.json').write_text(json.dumps({'case_id':case,'live_model':True,
            'automated_test_outcome':outcome.outcome if outcome else 'unknown',
            'semantic_review':'pending_separate_review',
            'automated_scope':'structure_evidence_execution',
            'required_semantic_checks':SEMANTIC_REVIEW_CHECKS},indent=2))
