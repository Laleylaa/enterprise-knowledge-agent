"""Actual Agent/function-tool execution, isolated from live API and local credentials."""

import os
import socket
from pathlib import Path

import pytest
from pydantic_ai import models

from knowledge_agent.config import Settings
from knowledge_agent.knowledge_base import IndexedCorpus
from knowledge_agent.runtime import create_turn_context

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def bound_state(monkeypatch, tmp_path, archive_run):
    for name in tuple(os.environ):
        if name.startswith("KA_") or name == "DEEPSEEK_API_KEY":
            monkeypatch.delenv(name)
    def blocked(*args, **kwargs):
        raise AssertionError("Tool integration tests must not use the network")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    def create(case_id, fixture="F1_single_rule", **overrides):
        settings = Settings(_env_file=None, mode="mock", output_dir=tmp_path / "runs",
                            corpus_path=ROOT / "data/fixtures" / fixture / "manifest.json",
                            tokenizer_path=tmp_path / "absent-tokenizer.json",
                            retrieval_cache_dir=tmp_path / "cache")
        settings = settings.model_copy(update=overrides)
        source = IndexedCorpus.load(settings.corpus_path, ROOT / "data/prepared" / f"{fixture}.json", settings)
        state = create_turn_context("请查询差旅报销相关制度原文。", settings, source)
        archive_run("integration", case_id, state.recorder.directory)
        return state
    return create
