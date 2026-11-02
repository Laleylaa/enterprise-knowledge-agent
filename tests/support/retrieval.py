"""Isolated fixtures used only by standalone retrieval tests."""

import os
import socket
import urllib.request
from pathlib import Path

import pytest
from pydantic_ai import Agent, models

from knowledge_agent.config import Settings
from knowledge_agent.retrieval.session import create_search_tool

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def retrieval_settings(monkeypatch, tmp_path):
    for key in tuple(os.environ):
        if key.startswith("KA_") or key == "DEEPSEEK_API_KEY":
            monkeypatch.delenv(key)

    def forbidden(*args, **kwargs):
        pytest.fail("Standalone retrieval tests must not call an Agent or the network")

    monkeypatch.setattr(Agent, "run", forbidden)
    monkeypatch.setattr(Agent, "run_sync", forbidden)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    return Settings(_env_file=None, retrieval_mode="bm25", tokenizer_path=tmp_path / "absent-tokenizer.json",
                    retrieval_cache_dir=tmp_path / "cache", output_dir=tmp_path / "runs")


@pytest.fixture
def tool_factory(retrieval_settings):
    def create(fixture="F1_single_rule", *, settings=None, corpus=None, prepared=None, output_dir=None):
        return create_search_tool(settings or retrieval_settings,
                                  corpus or ROOT / "data/fixtures" / fixture / "manifest.json",
                                  prepared or ROOT / "data/prepared" / f"{fixture}.json",
                                  output_dir=output_dir)
    return create
