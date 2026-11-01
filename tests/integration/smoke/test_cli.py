"""Startup, safe configuration and an actual offline CLI→agent→tool→result path."""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic_ai import models

from knowledge_agent.cli import main

pytestmark = pytest.mark.smoke
ROOT = Path(__file__).resolve().parents[3]


def test_module_entrypoint_help():
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    completed = subprocess.run([sys.executable, "-m", "knowledge_agent", "--help"],
                               env=env, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0
    assert "smoke" in completed.stdout and "config" in completed.stdout


def test_configuration_precedence_and_redaction(isolated_config, monkeypatch, capsys):
    (isolated_config / ".env").write_text("KA_MODE=mock\nKA_MODEL_NAME=from-file\n", encoding="utf-8")
    monkeypatch.setenv("KA_MODEL_NAME", "from-environment")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "smoke-secret-never-export")
    assert main(["config", "--mode", "real"]) == 0
    output = capsys.readouterr().out
    config = json.loads(output)
    assert config["mode"] == "real" and config["model_name"] == "from-environment"
    assert config["api_key_present"] is True
    assert "smoke-secret-never-export" not in output


def test_offline_end_to_end_without_network(isolated_config, monkeypatch, capsys, archive_run):
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    def block_network(*args, **kwargs):
        raise AssertionError("Offline smoke must not access the network")

    monkeypatch.setattr(socket.socket, "connect", block_network)
    monkeypatch.setattr(socket, "getaddrinfo", block_network)
    assert main(["smoke", "--mode", "mock"]) == 0
    result = json.loads(capsys.readouterr().out)
    directory = isolated_config / "runs/mock" / result["run_id"]
    archive_run("integration", "cli_mock", directory)
    assert result["mode"] == "mock" and result["result_origin"] == "mock"
    assert result["result"]["status"] == "resolved"
    assert result["usage"] == {"model_turns": 2, "http_attempts": 0, "tool_calls": 1}
    evidence = result["observed_evidence"][0]
    citation = result["result"]["citations"][0]
    assert evidence["delivered_to_model"] is True
    assert citation["evidence_id"] == evidence["evidence_id"] and citation["quote"] == evidence["text"]
    # The end-to-end path must use the agreed manifest + Markdown source format.
    manifest_path = ROOT / "data/smoke/manifest.json"
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))["documents"][0]
    assert "body" not in metadata
    original = (manifest_path.parent / metadata["source_path"]).read_bytes().decode("utf-8")
    snapshot = json.loads((directory / "corpus.json").read_text(encoding="utf-8"))
    assert snapshot["documents"][0] == {
        "doc_id": metadata["doc_id"], "title": metadata["title"],
        "version_date": metadata["version_date"], "body": original,
    }
    assert evidence["text"] == original and citation["quote"] in original
    assert json.loads((directory / "output.json").read_text()) == result
    requests = [json.loads(line) for line in (directory / "model-inputs.jsonl").read_text().splitlines()]
    assert len(requests) == 2
    assert any(part.get("part_kind") == "tool-return" for message in requests[1]["messages"] for part in message["parts"])
    events = [json.loads(line)["event_type"] for line in (directory / "trace.jsonl").read_text().splitlines()]
    assert events.index("tool_result") < events.index("result_candidate") < events.index("final_result")


def test_missing_key_is_explicit_and_does_not_fall_back(isolated_config, capsys):
    assert main(["smoke", "--mode", "real"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "real" and result["result_origin"] == "runtime_fallback"
    assert result["termination_reason"] == "missing_api_key"
    assert result["result"]["status"] == "incomplete"
    assert result["usage"]["http_attempts"] == 0


def test_invalid_configuration_fails_before_running(isolated_config, monkeypatch, capsys):
    monkeypatch.setenv("KA_MAX_MODEL_TURNS", "0")
    assert main(["smoke", "--mode", "mock"]) == 2
    assert "max_model_turns" in capsys.readouterr().err
    assert not (isolated_config / "runs").exists()
