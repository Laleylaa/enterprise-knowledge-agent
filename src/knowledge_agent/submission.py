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
        (output / 'README.md').write_text(f'''# 测试提交材料

自动测试：**{summary['passed']}/{summary['total']}通过，{summary['failed']}失败、{summary['errors']}错误、{summary['skipped']}跳过**。本批包含{summary['live_outputs']}轮真实回答、{summary['live_citations']}条真实回答引用。

- [测试汇总](summary.json)、[逐项测试结果](results.xml)
- [全部运行记录](cases.md)
- [测试预期、实际结果及限制](../../docs/03-evaluation.md)

## 文件说明

每次运行仅保留 `input.json`、`output.json`、`trace.jsonl`；共用文档原文及版本保存在 `corpora/`，通过输入中的相对路径定位。

输出中的业务结果保持原值；`export.raw_output_sha256` 标记原始输出文件。Trace是原始日志的确定性投影，保留实际模型动作、工具参数、返回摘要、补查、失败、重试、结束及中断，原始事件序号保持不变。`evidence_index` 给出证据对应的文档及字符区间，可从共用资料恢复原文；`reused_from` 关联跨轮证据。复用不计作新工具调用。

重复提示词、工具定义、累计模型消息及HTTP报文不进入提交包。测试仍使用完整运行记录进行断言，精简仅发生在导出阶段。脚本不会自动宣称语义评估通过。

## 复跑与生成

在仓库根目录执行（使用新的输出目录）：

```sh
mkdir -p runtime/evaluation/new-batch
.venv/bin/python -m pytest tests/contracts tests/e2e/offline -q --examples-dir runtime/evaluation/new-batch/offline --junitxml=runtime/evaluation/new-batch/offline-results.xml
PYTHONPATH=src .venv/bin/python -m knowledge_agent evaluate --mode real --retrieval hybrid --run-live --output-dir runtime/evaluation/new-batch/real
PYTHONPATH=src .venv/bin/python -m knowledge_agent.submission --source runtime/evaluation/new-batch --output examples/new-submission
```

环境和凭证见仓库README。真实模型输出及运行ID可能变化，文件结构和导出规则相同。历史完整材料可用同一打包命令转换，不会重新调用模型或改写业务答案。
''')
        return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.source, args.output), ensure_ascii=False, indent=2))
