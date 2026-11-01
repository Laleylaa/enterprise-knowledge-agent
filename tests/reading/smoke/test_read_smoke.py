"""Offline source reading through the public tool and standalone CLI."""

import json
import pytest

from knowledge_agent.reading.__main__ import main
from tests.support.retrieval import ROOT

pytestmark = pytest.mark.smoke


def test_read_prepared_source_without_tokenizer_or_model(reader_factory):
    tool = reader_factory()
    result = tool.execute({"doc_id": "D01", "purpose": "离线全文读取"}, call_id="smoke-read")
    assert result["status"] == "ok"
    assert "".join(s["text"] for s in result["data"]["segments"]) == tool.snapshot.get("D01").body
    run = json.loads((tool.recorder.directory / "run.json").read_text())
    assert run["stage"] == "standalone_read_tool" and run["model_calls"] == 0
    assert not (tool.recorder.directory / "model-inputs.jsonl").exists()
    assert all(not e.delivered_to_model for e in tool.evidence.snapshot())


@pytest.mark.parametrize("doc_id,code,status", [("D01", 0, "ok"), ("MISSING", 1, "error")])
def test_standalone_read_cli(retrieval_settings, monkeypatch, tmp_path, capsys, doc_id, code, status):
    monkeypatch.chdir(tmp_path)
    actual = main(["--corpus", str(ROOT / "data/fixtures/F1_single_rule/manifest.json"),
                   "--prepared", str(ROOT / "data/prepared/F1_single_rule.json"), "--doc-id", doc_id,
                   "--tokenizer-path", str(retrieval_settings.tokenizer_path),
                   "--output-dir", str(tmp_path / "cli-runs")])
    assert actual == code
    assert json.loads(capsys.readouterr().out)["status"] == status
