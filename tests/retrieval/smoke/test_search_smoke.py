"""Direct tool startup and CLI smoke, explicitly excluding the agent loop."""

import json

import pytest

from knowledge_agent.retrieval.__main__ import main
from tests.support.retrieval import ROOT

pytestmark = pytest.mark.smoke


def test_offline_search_from_prepared_markdown_without_tokenizer_or_model(tool_factory):
    tool = tool_factory()
    response = tool.execute({"query": "提交期限", "purpose": "单工具冒烟"}, call_id="smoke-1")
    assert response["status"] == "ok" and response["data"]["hits"]
    assert response["execution"]["strategy"] == "bm25"
    run = json.loads((tool.recorder.directory / "run.json").read_text())
    assert run["model_calls"] == 0 and run["stage"] == "standalone_search_tool"
    assert not (tool.recorder.directory / "model-inputs.jsonl").exists()
    assert all(not e.delivered_to_model for e in tool.evidence.snapshot())


def test_direct_search_cli_uses_offline_prepared_blocks(retrieval_settings, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)  # No local .env.
    monkeypatch.setenv("KA_RETRIEVAL_CACHE_DIR", str(retrieval_settings.retrieval_cache_dir))
    code = main(["search", "--corpus", str(ROOT / "data/fixtures/F1_single_rule/manifest.json"),
                 "--prepared", str(ROOT / "data/prepared/F1_single_rule.json"),
                 "--tokenizer-path", str(retrieval_settings.tokenizer_path),
                 "--query", "提交期限", "--output-dir", str(tmp_path / "cli-runs")])
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["tool"] == "search_knowledge" and output["data"]["hits"]
