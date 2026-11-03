# 验证材料

本目录保存提交版的实际运行证据。测试预期、业务结论和限制集中说明于[评估文档](../docs/03-evaluation.md)，安装与模型配置见[根 README](../README.md)。

## 批次与索引

| 批次 | 自动测试结果 | 真实模型记录 | 材料入口 |
| --- | --- | --- | --- |
| 完整验收 | 54 项通过，0 失败、错误或跳过 | 23 轮回答、30 条引用 | [汇总](submission-check/summary.json) · [逐项结果](submission-check/results.xml) · [运行记录](submission-check/cases.md) |

本批次包含基础契约 29 项、离线 Mock 7 项、真实业务必验 6 项和扩展 12 项。共保留 41 组实际运行记录，包含真实模型、Mock 与本地替身记录；测试项数与运行记录数分别统计。具体预期与实际行为见[两阶段状态与动态决策验证](../docs/03-evaluation.md#3-两阶段状态与动态决策验证)。

## 文件说明

每组记录通过用例名称和运行 ID 关联：

- `input.json`：当前问题、对话历史、运行配置，以及对应资料快照的相对路径。
- `output.json`：实际回答、引用、缺口、任务状态与调用统计。
- `trace.jsonl`：实际模型动作、工具参数、返回摘要、失败、补查、重试、结束与中断。
- 批次下的 `corpora/`：按资料版本共用的文档 ID、版本日期与原文。

输出中的业务结果保持原值。精简 Trace 保留原始事件序号，`evidence_index` 给出证据的文档与字符区间，`reused_from` 关联跨轮证据；原文可从资料快照恢复。重复提示词、工具定义和 HTTP 调试报文留在本地。自动检查通过不替代答案含义与引用支持关系的核对。

## 完整复跑与打包

按根 README 激活虚拟环境并设置环境变量后，在仓库根目录执行；先完成依赖、密钥和 hybrid 资产准备。以下单行命令适用于 macOS/Linux 与 Windows PowerShell。使用新的输出目录，保留每次执行的结果：

```sh
python -m pytest tests/contracts tests/e2e/offline -q --examples-dir runtime/evaluation/new-batch/offline --junitxml=runtime/evaluation/new-batch/offline-results.xml
python -m knowledge_agent evaluate --mode real --retrieval hybrid --run-live --output-dir runtime/evaluation/new-batch/real
python -m knowledge_agent.submission --source runtime/evaluation/new-batch --output runtime/new-submission
```

前两条测试命令分别运行 36 项基础与离线检查、18 项真实业务检查，共 54 项。复跑结果和导出包默认保存在本地 `runtime/`。打包脚本读取已有结果，生成 `summary.json`、`results.xml`、`cases.md`、各轮记录和共用资料；不重新调用模型，也不改写业务答案。真实模型的措辞和运行 ID 可能变化。
