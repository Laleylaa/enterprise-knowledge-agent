import json
import os
import pytest
from knowledge_agent import cli
from knowledge_agent.config import Settings
def test_default_modes_and_explicit_choices():
    assert Settings(_env_file=None).selected_retrieval == "hybrid"
    assert Settings(_env_file=None, mode="mock").selected_retrieval == "bm25"
    assert Settings(_env_file=None, mode="mock", retrieval_mode="bm25").selected_retrieval == "bm25"
    assert Settings(_env_file=None, retrieval_mode="bm25").selected_retrieval == "bm25"
    assert Settings(_env_file=None, retrieval_mode="vector").selected_retrieval == "vector"
    for mode in ("vector", "hybrid"):
        with pytest.raises(ValueError, match="Mock 仅支持 BM25"):
            Settings(_env_file=None, mode="mock", retrieval_mode=mode)

@pytest.mark.contract
def test_config_precedence_and_mode_defaults(monkeypatch, tmp_path, capsys):
    for key in tuple(os.environ):
        if key.startswith('KA_'):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    args = ['config', '--prepared', 'blocks.json']
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)['retrieval'] == 'hybrid'
    assert cli.main(args + ['--mode', 'mock']) == 0
    assert json.loads(capsys.readouterr().out)['retrieval'] == 'bm25'
    (tmp_path / '.env').write_text('KA_RETRIEVAL_MODE=vector\nKA_RRF_K=70\n')
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)['retrieval'] == 'vector'
    assert cli.main(args + ['--mode', 'mock']) == 2
    assert 'Mock 仅支持 BM25' in capsys.readouterr().err
    assert cli.main(args + ['--mode', 'mock', '--retrieval', 'bm25']) == 0
    assert json.loads(capsys.readouterr().out)['retrieval'] == 'bm25'
    monkeypatch.setenv('KA_RETRIEVAL_MODE', 'bm25')
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)['retrieval'] == 'bm25'
    assert cli.main(args + ['--retrieval', 'hybrid', '--rrf-k', '80']) == 0
    value = json.loads(capsys.readouterr().out)
    assert value['retrieval'] == 'hybrid' and value['rrf_k'] == 80


@pytest.mark.contract
@pytest.mark.parametrize('mode', ['vector', 'hybrid'])
def test_mock_chat_rejects_other_retrieval_before_startup(monkeypatch, tmp_path, capsys, mode):
    for key in tuple(os.environ):
        if key.startswith('KA_'):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    def unexpected_startup(*args, **kwargs):
        pytest.fail('Invalid Mock retrieval must not initialize tools or models')
    monkeypatch.setattr(cli, 'open_indexed_source', unexpected_startup)
    args = ['chat', '--mode', 'mock', '--scenario', 'normal']
    assert cli.main(args + ['--retrieval', mode]) == 2
    assert 'Mock 仅支持 BM25' in capsys.readouterr().err
    monkeypatch.setenv('KA_RETRIEVAL_MODE', mode)
    assert cli.main(args) == 2
    assert 'Mock 仅支持 BM25' in capsys.readouterr().err


def test_evaluation_selects_only_matching_e2e_suites():
    from knowledge_agent.evaluation import ROOT, resolve_suite
    assert resolve_suite(None, 'real') == str(ROOT / 'tests/e2e')
    assert resolve_suite(None, 'mock') == str(ROOT / 'tests/e2e/offline')
    for group in ('required', 'extended'):
        assert resolve_suite(str(ROOT / 'tests/e2e' / group), 'real').endswith(group)
    for mode, path in [('real', 'tests/e2e/offline'), ('mock', 'tests/e2e/required'), ('real', 'tests/contracts')]:
        with pytest.raises(ValueError):
            resolve_suite(str(ROOT / path), mode)
