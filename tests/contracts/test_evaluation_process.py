"""Exercise Windows cancellation with process doubles; no real Windows claim."""

import json
import subprocess
from unittest.mock import Mock

import pytest

from knowledge_agent import evaluation
from knowledge_agent.config import Settings


@pytest.fixture
def windows_process(monkeypatch):
    monkeypatch.setattr(evaluation, 'WINDOWS', True)
    monkeypatch.setattr(evaluation.signal, 'CTRL_BREAK_EVENT', 1, raising=False)
    monkeypatch.setattr(evaluation.subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200, raising=False)
    return Mock(pid=1234, returncode=2, poll=Mock(return_value=None))


def test_windows_evaluation_cancellation_saves_summary(monkeypatch, tmp_path, windows_process):
    process = windows_process
    process.wait.side_effect = [KeyboardInterrupt, 2]
    launch = Mock(return_value=process)
    monkeypatch.setattr(evaluation.subprocess, 'Popen', launch)
    settings = Settings(_env_file=None, mode='mock', retrieval_mode='bm25')
    summary = evaluation.evaluate(settings, output_dir=tmp_path)
    options = launch.call_args.kwargs
    assert options['creationflags'] == 0x200 and 'start_new_session' not in options
    assert options['env']['PYTHONUTF8'] == '1'
    assert 'DEEPSEEK_API_KEY' not in options['env']
    process.send_signal.assert_called_once_with(1)
    assert summary['status'] == 'cancelled' and summary['exit_code'] == 130
    assert not summary['automatic_checks_passed']
    saved = next(tmp_path.glob('*/summary.json'))
    assert json.loads(saved.read_text(encoding='utf-8')) == summary


@pytest.mark.parametrize('failure', ['timeout', 'no_console'])
def test_windows_cancellation_falls_back_to_bounded_tree_cleanup(monkeypatch, windows_process, failure):
    process = windows_process
    if failure == 'timeout':
        process.wait.side_effect = [subprocess.TimeoutExpired('pytest', 5), 1]
    else:
        process.send_signal.side_effect = OSError('console unavailable')
        process.wait.return_value = 1
    cleanup = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(evaluation.subprocess, 'run', cleanup)
    evaluation.stop_evaluation(process)
    assert cleanup.call_args.args[0] == ['taskkill', '/PID', '1234', '/T', '/F']
    assert cleanup.call_args.kwargs['timeout'] == 5
    assert process.wait.call_args.kwargs['timeout'] == 2


def test_windows_cleanup_failure_is_reported(monkeypatch, windows_process):
    windows_process.send_signal.side_effect = OSError('console unavailable')
    windows_process.wait.side_effect = subprocess.TimeoutExpired('pytest', 2)
    monkeypatch.setattr(evaluation.subprocess, 'run', Mock(return_value=subprocess.CompletedProcess([], 1)))
    with pytest.raises(RuntimeError, match='进程树清理失败'):
        evaluation.stop_evaluation(windows_process)


def test_windows_already_exited_process_is_not_signalled(windows_process):
    windows_process.poll.return_value = 0
    evaluation.stop_evaluation(windows_process)
    windows_process.send_signal.assert_not_called()
    windows_process.wait.assert_not_called()
