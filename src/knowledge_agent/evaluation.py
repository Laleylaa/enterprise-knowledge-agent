"""Run the repository's existing acceptance suites in an isolated pytest process."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from uuid import uuid4

from knowledge_agent.trace import RunRecorder

ROOT = Path(__file__).resolve().parents[2]


def resolve_suite(suite, mode):
    expected = ROOT / 'tests/e2e'
    if mode == 'mock':
        expected /= 'offline'
    value = suite or str(expected)
    path, *node = value.split('::')
    target = Path(path).resolve()
    allowed = mode == 'mock' or target == expected.resolve() or any(
        target.is_relative_to((expected / group).resolve()) for group in ('required', 'extended'))
    if not target.exists() or not target.is_relative_to(expected.resolve()) or not allowed:
        raise ValueError(f'evaluate --mode {mode} 只接受 {expected.relative_to(ROOT)} 内的目录、文件或测试节点。')
    if target.is_file() and target.suffix != '.py':
        raise ValueError('评估 suite 必须是测试目录或 Python 测试文件。')
    return '::'.join([str(target), *node])


def stop_evaluation(process):
    """Give pytest time to save interrupted results, then stop its worker group."""
    for sig, timeout in ((signal.SIGINT, 5), (signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=timeout)
            # Stop any remaining children even when pytest already exited.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return
        except subprocess.TimeoutExpired:
            continue
    raise RuntimeError('评估子进程未能在终止时限内退出。')


def summarize(pytest_code, facts, *, collect_only=False, cancelled=False):
    counts = {key: int(facts.get(key, 0)) for key in ('collected', 'deselected', 'passed', 'failed', 'errors', 'skipped')}
    if cancelled:
        status, code = 'cancelled', 130
    elif pytest_code != 0:
        status, code = ('no_tests' if pytest_code == 5 else 'failed'), pytest_code
    elif not facts:
        status, code = 'report_missing', 2
    elif collect_only:
        status, code = 'collected', 0
    elif counts['failed'] or counts['errors']:
        status, code = 'failed', 1
    elif counts['passed'] == 0:
        status, code = 'not_executed', 5
    elif counts['skipped'] or counts['passed'] < counts['collected']:
        status, code = 'incomplete', 1
    else:
        status, code = 'passed', 0
    return {'status': status, 'exit_code': code, 'pytest_exit_code': pytest_code, 'counts': counts,
            'automatic_checks_passed': status == 'passed', 'semantic_review': 'not_performed',
            'overall_acceptance': 'not_assessed'}


def observed_runs(directory):
    """Report actual run identities and degradation separately from test assertions."""
    runs, modes, degraded = [], set(), 0
    for path in sorted((directory / 'artifacts/e2e/outputs').glob('*/*/output.json')):
        result = json.loads(path.read_text())
        modes.add(result['requested_retrieval'])
        runs.append({'run_id': result['run_id'], 'mode': result['mode'],
                     'retrieval': result['requested_retrieval'], 'origin': result['result_origin'],
                     'status': result['result']['status'], 'usage': result['usage'],
                     'output': str(path.relative_to(directory))})
    for path in (directory / 'artifacts/e2e/traces').glob('*/*/tool-results.jsonl'):
        for line in path.read_text().splitlines():
            value = json.loads(line)
            if value['tool'] == 'search_knowledge' and any(
                    (e.get('target') or {}).get('kind') == 'branch' for e in value['errors']):
                degraded += 1
    return {'runs': runs, 'observed_retrieval_modes': sorted(modes),
            'search_calls_with_branch_errors': degraded,
            'retrieval_observation': 'not_observed' if not runs else 'branch_errors_present' if degraded else 'no_branch_errors_observed'}


def evaluate(settings, *, suite=None, run_live=False, collect_only=False, selection=None, output_dir=None):
    target = resolve_suite(suite, settings.mode)
    if settings.mode == 'real' and not collect_only and not run_live:
        raise ValueError('真实评估会调用模型服务；执行需显式 --run-live，或使用 --collect-only 仅收集用例。')
    if settings.mode == 'mock' and run_live:
        raise ValueError('Mock 评估不能启用 --run-live。')
    if settings.mode == 'real' and run_live and not collect_only and not settings.has_api_key:
        raise ValueError('真实评估需要本地 DEEPSEEK_API_KEY，未启动测试。')
    config = settings.model_dump(mode='json', exclude={'deepseek_api_key'})
    # Test suites own corpus/scenario/output; these CLI values would otherwise be ignored.
    config['mock_scenario'] = None
    for name in ('embedding_model_path', 'tokenizer_path', 'retrieval_cache_dir'):
        config[name] = str(Path(config[name]).resolve())
    identity = uuid4().hex
    directory = (output_dir or Path('examples/evaluation')).resolve() / identity
    recorder = RunRecorder(directory, identity)
    recorder.write('settings.json', config)
    command = [sys.executable, '-m', 'pytest', target, '-q',
               '--evaluation-config', str(directory / 'settings.json'),
               '--evaluation-facts', str(directory / 'test-facts.json'),
               '--junitxml', str(directory / 'results.xml'), '--examples-dir', str(directory / 'artifacts')]
    if settings.mode == 'real':
        command.extend(['--ignore', str(ROOT / 'tests/e2e/offline')])
    if collect_only:
        command.append('--collect-only')
    elif run_live:
        command.append('--run-live')
    if selection is not None:
        command.extend(['-k', selection])
    recorder.write('input.json', {'suite': target, 'mode': settings.mode, 'retrieval': settings.selected_retrieval,
                                 'collect_only': collect_only, 'live_enabled': run_live and not collect_only,
                                 'selection': selection, 'command': command})
    env = dict(os.environ)
    # A caller's pytest flags/plugins must not silently enable live tests or change selection.
    env.pop('PYTEST_ADDOPTS', None)
    env.pop('PYTEST_PLUGINS', None)
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT), str(ROOT / 'src')])
    if settings.has_api_key and settings.mode == 'real':
        env['DEEPSEEK_API_KEY'] = settings.deepseek_api_key.get_secret_value()
    else:
        env.pop('DEEPSEEK_API_KEY', None)
    cancelled = False
    launch_failed = False
    recorder.event('evaluation_started', mode=settings.mode, retrieval=settings.selected_retrieval)
    print(f'评估材料：{directory}', file=sys.stderr)
    with (directory / 'pytest.log').open('w', encoding='utf-8') as log:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        except OSError:
            launch_failed, code = True, 2
            recorder.event('evaluation_launch_failed')
        else:
            try:
                code = process.wait()
            except KeyboardInterrupt:
                cancelled = True
                stop_evaluation(process)
                code = process.returncode
            except BaseException:
                stop_evaluation(process)
                raise
    facts_path = directory / 'test-facts.json'
    facts = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    summary = {**summarize(code, facts, collect_only=collect_only, cancelled=cancelled),
               **observed_runs(directory),
               'evaluation_id': identity, 'directory': str(directory), 'mode': settings.mode,
               'requested_retrieval': settings.selected_retrieval, 'suite': target}
    if launch_failed:
        summary['status'] = 'launch_failed'
    if set(summary['observed_retrieval_modes']) - {settings.selected_retrieval}:
        summary.update(status='retrieval_mismatch', exit_code=1, automatic_checks_passed=False)
    recorder.write('summary.json', summary)
    recorder.event('evaluation_finished', status=summary['status'], exit_code=summary['exit_code'])
    return summary
