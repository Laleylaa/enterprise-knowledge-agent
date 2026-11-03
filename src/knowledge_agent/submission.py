"""Build a small, reproducible submission bundle from existing test artifacts."""

import argparse
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

from knowledge_agent.artifact_export import FORMAT, convert_archive, save


def publish(source: Path, output: Path):
    source, output = source.resolve(), output.resolve()
    if not source.is_dir() or output.exists() or output.is_relative_to(source):
        raise ValueError('Source must exist; output must be a new directory outside the source')
    with TemporaryDirectory(prefix='knowledge-submission-') as temporary:
        work = source
        if any(source.rglob('artifacts.json')):
            work = (Path(temporary) / 'converted').resolve()
            convert_archive(source, work)
        rows = []
        for path in sorted(work.rglob('output.json')):
            if path.parent.parent.parent.name != 'outputs':
                continue
            result = json.loads(path.read_text())
            if result.get('export', {}).get('format') != FORMAT:
                raise ValueError(f'Unsupported evidence format: {path}')
            scope, case, run = path.parents[3], path.parent.parent.name, path.parent.name
            inp_path = scope / 'inputs' / case / run / 'input.json'
            trace_path = scope / 'traces' / case / run / 'trace.jsonl'
            inp = json.loads(inp_path.read_text())
            target = output / 'cases' / case / run
            target.mkdir(parents=True, exist_ok=False)
            if inp.get('corpus'):
                corpus = (inp_path.parent / inp['corpus']).resolve()
                if not corpus.is_relative_to(work):
                    raise ValueError('Corpus reference escapes source evidence')
                dest = output / 'corpora' / corpus.name
                save(dest, json.loads(corpus.read_text()))
                inp['corpus'] = os.path.relpath(dest, target)
            save(target / 'input.json', inp)
            shutil.copyfile(path, target / 'output.json')
            shutil.copyfile(trace_path, target / 'trace.jsonl')
            business = result.get('result', {})
            rows.append({'case': case, 'run_id': run, 'turn': result.get('turn_id'),
                         'mode': result.get('mode', result.get('model_origin')),
                         'live_model': inp.get('test', {}).get('live_model', False),
                         'status': business.get('status', result.get('stopped_after', 'boundary_check')),
                         'citations': len(business.get('citations', [])),
                         'usage': result.get('usage', {}),
                         'path': target.relative_to(output).as_posix()})
        if not rows:
            raise ValueError('No compact test runs found')
        # Keep individual pytest outcomes, including failures/skips, in one JUnit file.
        combined = ET.Element('testsuites')
        counts = dict(tests=0, failures=0, errors=0, skipped=0)
        for path in sorted(source.rglob('*.xml')):
            if path.name not in {'results.xml', 'offline-results.xml'}:
                continue
            root = ET.parse(path).getroot()
            for suite in ([root] if root.tag == 'testsuite' else list(root.findall('testsuite'))):
                combined.append(suite)
                for key in counts:
                    counts[key] += int(suite.get(key, 0))
        if not counts['tests']:
            raise ValueError('No JUnit results found; cannot infer test success from outputs')
        ET.ElementTree(combined).write(output / 'results.xml', encoding='utf-8', xml_declaration=True)
        summary = {'format': FORMAT, 'total': counts['tests'],
                   'passed': counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped'],
                   'failed': counts['failures'], 'errors': counts['errors'], 'skipped': counts['skipped'],
                   'run_records': len(rows), 'live_outputs': sum(r['live_model'] for r in rows),
                   'live_citations': sum(r['citations'] for r in rows if r['live_model']),
                   'semantic_review': 'not_automatically_assessed',
                   'results': 'results.xml', 'runs': 'cases.md'}
        save(output / 'summary.json', summary)
        table = ['# 实际运行记录', '',
                 '表格由导出脚本读取实际运行结果生成；状态与自动测试结果不代替答案语义评估。每个输入链接均可定位共用资料快照。', '',
                 '| 场景 | 轮次 | 模式 | 状态 | 工具调用 | 输入、输出与Trace |',
                 '| --- | ---: | --- | --- | ---: | --- |']
        for row in sorted(rows, key=lambda r: (r['case'], r['turn'] or 0, r['run_id'])):
            links = ' · '.join(f'[{label}]({row["path"]}/{name})' for label, name in
                               [('输入', 'input.json'), ('输出', 'output.json'), ('Trace', 'trace.jsonl')])
            mode = '真实模型' if row['live_model'] else '离线Mock' if row['mode'] == 'mock' else '本地替身'
            table.append(f'| {row["case"]} | {row["turn"] or "—"} | {mode} | {row["status"]} | {row["usage"].get("tool_calls", "—")} | {links} |')
        (output / 'cases.md').write_text('\n'.join(table) + '\n')
        return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.source, args.output), ensure_ascii=False, indent=2))
