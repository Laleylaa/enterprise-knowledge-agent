"""Q15: formal CLI + production SDK + explicit local HTTP faults, never live failures."""
import json
import os
import socket
from pathlib import Path

import httpx2
import pytest
from openai import AsyncOpenAI
from pydantic_ai import models

from knowledge_agent import model_adapter
from knowledge_agent.cli import main

ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.boundary


@pytest.mark.parametrize('failure,attempts',[('timeout',2),('authentication',1)])
def test_Q15_formal_chat_http_failures(monkeypatch,tmp_path,capsys,archive_run,failure,attempts):
    for key in tuple(os.environ):
        if key.startswith('KA_') or key=='DEEPSEEK_API_KEY':monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DEEPSEEK_API_KEY','local-injected-test-key')
    monkeypatch.setenv('KA_RETRIEVAL_CACHE_DIR',str(tmp_path/'cache'))
    def block(*args,**kwargs):raise AssertionError('Injected transport must never use network')
    monkeypatch.setattr(socket.socket,'connect',block)
    monkeypatch.setattr(socket,'getaddrinfo',block)
    monkeypatch.setattr(models,'ALLOW_MODEL_REQUESTS',True)
    requests=[];clients=[]
    def transport(request):
        requests.append(json.loads(request.content))
        if failure=='timeout':raise httpx2.ReadTimeout('local injected timeout')
        return httpx2.Response(401,json={'error':{'message':'private injected body'}})
    def factory(**kwargs):
        assert kwargs['max_retries']==0
        client=AsyncOpenAI(**kwargs,http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(transport)))
        clients.append(client);return client
    monkeypatch.setattr(model_adapter,'AsyncOpenAI',factory)
    output=tmp_path/'runs'
    try:
        code=main(['chat','--mode','real','--retrieval','bm25','--format','json','--question','国内差旅报销期限多久？',
            '--corpus',str(ROOT/'data/fixtures/F1_single_rule/manifest.json'),
            '--prepared',str(ROOT/'data/prepared/F1_single_rule.json'),'--output-dir',str(output)])
    finally:
        for path in (output/'real').glob('*/output.json'):
            (path.parent/'run.json').write_text(json.dumps({'scope':'formal_cli_http_injection','mode':'real',
                'live_model':False,'model_origin':'local_http_fault','failure':failure,'network_blocked':True}))
            (path.parent/'fault-injection.json').write_text(json.dumps({'failure':failure,'attempts':len(requests),'provider':'local_http_transport'}))
            (path.parent/'provider-requests.json').write_text(json.dumps(requests,ensure_ascii=False))
            archive_run('integration','Q15_'+failure,path.parent)
    captured=capsys.readouterr();r=json.loads(captured.out)
    assert code==1 and r['result']['status']=='incomplete' and r['termination_reason']=='model_request_failed'
    assert r['result_origin']=='runtime_fallback' and r['mode']=='real'
    assert r['usage']=={'model_turns':1,'http_attempts':attempts,'tool_calls':0}
    assert len(requests)==attempts and all(c.is_closed() for c in clients)
    assert not r['observed_evidence'] and not r['result']['citations']
    assert {t['function']['name'] for t in requests[0]['tools']}=={'search_knowledge','read_document','submit_answer'}
    if attempts==2:assert requests[0]==requests[1]
    assert 'local-injected-test-key' not in captured.out and 'private injected body' not in captured.out
