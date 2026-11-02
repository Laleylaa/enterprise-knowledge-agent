"""Q16/Q17: production CLI + explicit script + actual BM25/reader, no network."""
import json
import os
import socket
from pathlib import Path

import pytest
from pydantic_ai import models

from knowledge_agent.cli import main
from knowledge_agent.offline_scenarios import QUESTIONS
from tests.support.single_turn import audit_run
from tests.support.evaluation import apply_evaluation

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture
def offline_cli(monkeypatch,tmp_path,capsys,archive_run,request,evaluation_settings):
    for key in tuple(os.environ):
        if key.startswith('KA_') or key=='DEEPSEEK_API_KEY':monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    def block(*args,**kwargs):raise AssertionError('Offline CLI attempted network access')
    monkeypatch.setattr(socket.socket,'connect',block)
    monkeypatch.setattr(socket,'getaddrinfo',block)
    monkeypatch.setattr(models,'ALLOW_MODEL_REQUESTS',False)
    monkeypatch.setenv('KA_TOKENIZER_PATH',str(tmp_path/'no-tokenizer.json'))
    monkeypatch.setenv('KA_RETRIEVAL_CACHE_DIR',str(tmp_path/'empty-cache'))
    retrieval=apply_evaluation(monkeypatch,evaluation_settings,default_retrieval="bm25")
    root=tmp_path/'runs'
    pending=[]
    def execute(scenario,fixture='F1_single_rule',question=None,interactive=None):
        case='offline_'+scenario
        args=['chat','--mode','mock','--scenario',scenario,'--format','json',
              '--corpus',str(ROOT/'data/fixtures'/fixture/'manifest.json'),
              '--prepared',str(ROOT/'data/prepared'/f'{fixture}.json'),'--output-dir',str(root)]
        if interactive is None:args.extend(['--question',question if question is not None else QUESTIONS[scenario]])
        else:
            seq=iter(interactive);monkeypatch.setattr('builtins.input',lambda:next(seq))
        try:code=main(args)
        finally:
            for p in (root/'mock').glob('*/output.json'):
                if p.parent in pending:continue
                pending.append(p.parent)
                (p.parent/'run.json').write_text(json.dumps({'scope':'formal_offline_cli','live_model':False,
                    'model_origin':'production_script','scenario':scenario,'test_id':request.node.nodeid,'network_blocked':True,
                    'credentials_present':False,'tokenizer_cache_present':Path(os.environ['KA_TOKENIZER_PATH']).is_file(),
                    'retrieval':retrieval}))
                archive_run('e2e',case,p.parent)
        captured=capsys.readouterr()
        outputs=[json.loads(line) for line in captured.out.splitlines()]
        return code,outputs,captured.err
    execute.root=root
    execute.retrieval=retrieval
    yield execute
    for path in (root/'mock/sessions').glob('*'):
        archive_run('e2e','offline_session',path)


@pytest.mark.smoke
@pytest.mark.parametrize('scenario,fixture,status',[
 ('normal','F1_single_rule','resolved'),('conflict','F2_conflicting_rules','needs_info'),
 ('missing','F1_single_rule','unresolved'),('tool_failure','F1_single_rule','incomplete'),
 ('recovery','F1_single_rule','resolved'),('budget','F1_single_rule','incomplete')])
def test_formal_offline_scenarios(offline_cli,scenario,fixture,status):
    code,results,_=offline_cli(scenario,fixture)
    assert code==(1 if status=='incomplete' else 0)
    r=results[0];assert r['mode']=='mock' and r['mock_scenario']==scenario
    assert r['result']['status']==status and r['usage']['http_attempts']==0
    records=audit_run(offline_cli.root/'mock'/r['run_id'],r,expected_retrieval=offline_cli.retrieval)
    assert r['result_origin']==('runtime_fallback' if scenario=='budget' else 'mock')
    assert r['usage']['tool_calls']>0
    if scenario=='conflict':
        assert {c['doc_id'] for c in r['result']['citations']}=={'D01','D02'}
        stops = [e['payload']['result']['reason'] for e in records['events']
                 if e['event_type']=='research_complete']
        assert stops == ['conflict']
    if scenario=='tool_failure':
        assert records['returns'][0]['errors'][0]['code']=='READ_FAILED'
        assert not r['observed_evidence']
    if scenario=='recovery':
        assert records['returns'][0]['errors'][0]['code']=='SEARCH_FAILED'
        assert records['returns'][1]['tool']=='read_document' and records['returns'][1]['status']=='ok'
        assert '30 天' in r['result']['answer']
    if scenario=='missing':assert records['returns'][0]['errors'][0]['code']=='NOT_FOUND'
    if scenario=='budget':assert r['termination_reason']=='model_turn_limit'


@pytest.mark.contract
def test_unsupported_input_is_explicit_and_creates_no_run(offline_cli):
    code,outputs,error=offline_cli('normal',question='写一首诗')
    assert code==2 and not outputs and 'MOCK_SCENARIO_UNSUPPORTED' in error
    assert not list((offline_cli.root/'mock').glob('*/output.json'))
