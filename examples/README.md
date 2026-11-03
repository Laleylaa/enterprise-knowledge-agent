# 验证材料

本目录保存提交版的实际运行证据。测试预期、业务结论和限制集中说明于[评估文档](../docs/03-evaluation.md)，安装与模型配置见[根 README](../README.md)。

## 批次与索引

| 批次 | 自动测试结果 | 真实模型记录 | 材料入口 |
| --- | --- | --- | --- |
| 完整验收 | 49 项通过，0 失败、错误或跳过 | 23 轮回答、28 条引用 | [汇总](submission-check/summary.json) · [逐项结果](submission-check/results.xml) · [运行记录](submission-check/cases.md) |
| 定向复测 | 4 个既有用例各执行 3 次，共 12 次通过 | 15 轮回答、30 条引用 | [固定计划](submission-check/repeat-check/plan.json) · [汇总](submission-check/repeat-check/summary.json) · [逐项结果](submission-check/repeat-check/results.xml) · [运行记录](submission-check/repeat-check/cases.md) |

完整批次另含 Mock 与本地替身，共 41 组运行记录。定向复测单独计数，不累加到 49 项中；它验证文档冲突、较新版本冲突、通知追问和明确适用范围。具体预期与实际行为见[两阶段状态与动态决策验证](../docs/03-evaluation.md#3-两阶段状态与动态决策验证)。

## 文件说明

每组记录通过用例名称和运行 ID 关联：

- `input.json`：当前问题、对话历史、运行配置，以及对应资料快照的相对路径。
- `output.json`：实际回答、引用、缺口、任务状态与调用统计。
- `trace.jsonl`：实际模型动作、工具参数、返回摘要、失败、补查、重试、结束与中断。
- 批次下的 `corpora/`：按资料版本共用的文档 ID、版本日期与原文。

输出中的业务结果保持原值。精简 Trace 保留原始事件序号，`evidence_index` 给出证据的文档与字符区间，`reused_from` 关联跨轮证据；原文可从资料快照恢复。重复提示词、工具定义和 HTTP 调试报文留在本地。自动检查通过不替代答案含义与引用支持关系的核对。

## 完整复跑与打包

在仓库根目录执行，先完成依赖、密钥和 hybrid 资产准备。使用新的输出目录，保留每次执行的结果：

```sh
mkdir -p runtime/evaluation/new-batch
.venv/bin/python -m pytest tests/contracts tests/e2e/offline -q --examples-dir runtime/evaluation/new-batch/offline --junitxml=runtime/evaluation/new-batch/offline-results.xml
PYTHONPATH=src .venv/bin/python -m knowledge_agent evaluate --mode real --retrieval hybrid --run-live --output-dir runtime/evaluation/new-batch/real
PYTHONPATH=src .venv/bin/python -m knowledge_agent.submission --source runtime/evaluation/new-batch --output examples/new-submission
```

前两条测试命令分别运行 31 项基础与离线检查、18 项真实业务检查。打包脚本读取已有结果，生成 `summary.json`、`results.xml`、`cases.md`、各轮记录和共用资料；不重新调用模型，也不改写业务答案。真实模型的措辞和运行 ID 可能变化。

## 定向复测

预先固定执行 3 轮，每轮运行相同的 4 个用例，并保留全部轮次：

```sh
for round in 1 2 3; do
  PYTHONPATH=src .venv/bin/python -m knowledge_agent evaluate --mode real --retrieval hybrid --run-live -k 'test_conflicting_documents or test_Q02_newer_date or test_notification_without_channel or test_scope_lookup' --output-dir "runtime/evaluation/new-repeat-check/$round"
done
PYTHONPATH=src .venv/bin/python -m knowledge_agent.submission --source runtime/evaluation/new-repeat-check --output examples/new-repeat-check
```

这些重复运行用于检查既有冲突与适用关系场景，不代表长期稳定性评估。
