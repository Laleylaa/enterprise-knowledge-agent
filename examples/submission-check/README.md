# 测试提交材料

自动测试：**49/49通过，0失败、0错误、0跳过**。本批包含23轮真实回答、28条真实回答引用。

另附[取证与回复职责定向复测](repeat-check/README.md)：4个既有用例各固定执行3次，12次均通过，不累加到本报告49项中。[源文件核对](source-check.json)覆盖本次完整回归和定向复测。

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
