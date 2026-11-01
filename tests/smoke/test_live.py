"""Opt-in real-model integration smoke; not business acceptance or reliability proof."""

import asyncio
from pathlib import Path

import pytest

from knowledge_agent.config import load_settings
from knowledge_agent.corpus import FixtureCorpus
from knowledge_agent.mock_model import SMOKE_QUESTION
from knowledge_agent.runtime import run_turn

pytestmark = [pytest.mark.smoke, pytest.mark.live]
ROOT = Path(__file__).resolve().parents[2]


def test_real_model_tool_observation_and_output():
    settings = load_settings(
        mode="real",
        corpus_path=ROOT / "data/smoke/manifest.json",
        output_dir=ROOT / "examples/tests/smoke/runs",
    )
    if not settings.has_api_key:
        pytest.fail("--run-live requires DEEPSEEK_API_KEY in the environment or local .env")
    source = FixtureCorpus.load(settings.corpus_path, settings.max_tool_chars)
    result = asyncio.run(run_turn(SMOKE_QUESTION, settings, source))
    assert result.result_origin == "model", result.termination_reason
    assert result.usage.model_turns >= 2 and result.usage.tool_calls >= 1
    assert result.usage.http_attempts >= 2
    assert result.result.status == "resolved" and result.result.citations
    assert any(item.delivered_to_model for item in result.observed_evidence)
