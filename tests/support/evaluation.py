"""Optional pytest adapter; expectations remain solely in existing test suites."""

import json
from pathlib import Path
import signal

import pytest

from knowledge_agent.config import Settings


def pytest_addoption(parser):
    parser.addoption('--evaluation-config', default=None)
    parser.addoption('--evaluation-facts', default=None)


def pytest_configure(config):
    if config.getoption('--evaluation-config') and hasattr(signal, 'SIGBREAK'):
        # Let pytest save interrupted results when the Windows parent forwards Ctrl+C.
        previous = signal.signal(signal.SIGBREAK, signal.default_int_handler)
        config.add_cleanup(lambda: signal.signal(signal.SIGBREAK, previous))


@pytest.fixture
def evaluation_settings(request):
    path = request.config.getoption('--evaluation-config')
    return Settings(_env_file=None, **json.loads(Path(path).read_text(encoding='utf-8'))) if path else None


def pytest_sessionfinish(session, exitstatus):
    destination = session.config.getoption('--evaluation-facts')
    if not destination:
        return
    stats = session.config.pluginmanager.get_plugin('terminalreporter').stats
    summary = {'collected': session.testscollected, 'deselected': len(stats.get('deselected', [])),
               'passed': len(stats.get('passed', [])), 'failed': len(stats.get('failed', [])),
               'errors': len(stats.get('error', [])), 'skipped': len(stats.get('skipped', [])),
               'pytest_exit_code': int(exitstatus),
               'items': [item.nodeid for item in session.items]}
    Path(destination).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def apply_evaluation(monkeypatch, settings, *, default_retrieval='hybrid'):
    """Reapply selected runtime options after a test clears its environment."""
    mode = settings.selected_retrieval if settings else default_retrieval
    if settings:
        excluded = {'deepseek_api_key', 'mode', 'mock_scenario', 'corpus_path', 'prepared_path', 'output_dir',
                    'retrieval_mode', 'thinking'}
        for key, value in settings.model_dump(mode='json', exclude=excluded).items():
            if value is not None:
                monkeypatch.setenv('KA_' + key.upper(), str(value).lower() if isinstance(value, bool) else str(value))
    monkeypatch.setenv('KA_RETRIEVAL_MODE', mode)
    return mode
