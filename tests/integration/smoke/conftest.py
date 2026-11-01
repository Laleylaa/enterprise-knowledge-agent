from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    """Never read a developer's .env, or inherit their model/budget settings."""
    import os

    for key in tuple(os.environ):
        if key.startswith("KA_") or key == "DEEPSEEK_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KA_CORPUS_PATH", str(ROOT / "data/smoke/manifest.json"))
    monkeypatch.setenv("KA_OUTPUT_DIR", str(tmp_path / "runs"))
    return tmp_path
