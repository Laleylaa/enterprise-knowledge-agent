from tests.support.retrieval import retrieval_settings, tool_factory


from knowledge_agent.reading.session import create_read_tool
from tests.support.retrieval import ROOT
import json
import pytest


@pytest.fixture
def reader_factory(retrieval_settings):
    def create(fixture="F1_single_rule", *, settings=None, corpus=None, prepared=None):
        return create_read_tool(settings or retrieval_settings,
                                corpus or ROOT / "data/fixtures" / fixture / "manifest.json",
                                prepared or ROOT / "data/prepared" / f"{fixture}.json")
    return create





import os
import socket
from pathlib import Path

import pytest
from pydantic_ai import models

from knowledge_agent.config import Settings
from knowledge_agent.knowledge_base import IndexedCorpus
from knowledge_agent.runtime import create_turn_context

ROOT = Path(__file__).resolve().parents[2]


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
        settings = Settings(_env_file=None, mode="mock", retrieval_mode="bm25", output_dir=tmp_path / "runs",
                            corpus_path=ROOT / "data/fixtures" / fixture / "manifest.json",
                            tokenizer_path=tmp_path / "absent-tokenizer.json",
                            retrieval_cache_dir=tmp_path / "cache")
        settings = settings.model_copy(update=overrides)
        source = IndexedCorpus.load(settings.corpus_path, ROOT / "data/prepared" / f"{fixture}.json", settings)
        state = create_turn_context("请查询差旅报销相关制度原文。", settings, source)
        archive_run("integration", case_id, state.recorder.directory)
        return state
    return create



import os
import socket
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from pydantic_ai import models
from pydantic_ai.models.function import FunctionModel

from knowledge_agent.config import Settings
from knowledge_agent.corpus import FixtureCorpus
from knowledge_agent.runtime import run_turn

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def loop_environment(monkeypatch, tmp_path):
    for key in tuple(os.environ):
        if key.startswith("KA_") or key == "DEEPSEEK_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    def block_network(*args, **kwargs):
        raise AssertionError("Loop contract tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", block_network)
    monkeypatch.setattr(socket, "getaddrinfo", block_network)
    settings = Settings(_env_file=None, mode="mock", output_dir=tmp_path / "runs",
                        corpus_path=ROOT / "data/smoke/manifest.json")
    source = FixtureCorpus.load(settings.corpus_path, settings.max_tool_chars)
    return settings, source


@pytest.fixture
def local_model_factory():
    def build(respond):
        @asynccontextmanager
        async def factory(config):
            yield FunctionModel(respond, model_name="scripted-execution-boundary-contract")
        return factory
    return build


@pytest.fixture
def read_run_records():
    def read(settings, result):
        directory = settings.output_dir / result.mode / result.run_id
        records = {}
        for name in ("trace", "model-inputs", "tool-results"):
            path = directory / f"{name}.jsonl"
            records[name] = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        assert json.loads((directory / "output.json").read_text()) == result.model_dump(mode="json")
        assert records["trace"][-1]["event_type"] == "final_result"
        return records
    return read


@pytest.fixture
def run_loop(loop_environment, local_model_factory, read_run_records):
    def run(respond, **overrides):
        settings, source = loop_environment
        settings = settings.model_copy(update=overrides)
        result = asyncio.run(run_turn("国内差旅报销期限多久？", settings, source,
                                      model_factory=local_model_factory(respond)))
        return result, read_run_records(settings, result)
    return run
