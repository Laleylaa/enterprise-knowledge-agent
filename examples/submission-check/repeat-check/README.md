# 取证与回复职责定向复测

当前版本预先固定执行3轮，每轮运行4个既有用例，共12次测试执行，全部通过。这是49项提交版测试的重复验证，不新增测试项，也不计入主报告的49项汇总。

| 场景 | 取证预期与实测 | 回复预期与实测 |
| --- | --- | --- |
| 30天与15天冲突 | 观察冲突后继续查证，仍未消解时conflict | 保留双方引用，needs_info并追问适用线索 |
| 较新版本仍无适用依据 | 继续查证，conflict，不凭日期裁决 | needs_info，不擅自选择较新制度 |
| 用户说明没有更多线索 | 首轮及追问后都为conflict | 首轮needs_info，追问后unresolved且不重复追问 |
| 查到明确适用说明 | sufficient | 依据D03与D01回答国内30天，resolved |

每种场景3次均符合上述断言。共15轮真实回答、30条引用，经AI辅助阅读核对，未发现擅自选定冲突条款或无依据期限。

[固定计划与各轮结果](plan.json) · [汇总](summary.json) · [逐项结果](results.xml) · [全部输入、输出与Trace](cases.md)

所有用例使用真实模型与hybrid检索。自动检查取证原因、最终任务状态、冲突后的查证动作及原文引用；答案措辞另经AI辅助阅读。

复现时预先固定轮数，保留所有轮次：

```sh
for round in 1 2 3; do
  PYTHONPATH=src .venv/bin/python -m knowledge_agent evaluate --mode real --retrieval hybrid --run-live -k 'test_conflicting_documents or test_Q02_newer_date or test_notification_without_channel or test_scope_lookup' --output-dir "runtime/evaluation/new-repeat-check/$round"
done
PYTHONPATH=src .venv/bin/python -m knowledge_agent.submission --source runtime/evaluation/new-repeat-check --output examples/new-repeat-check
```

原始输出未改写，Trace为实际日志的精简投影；共用资料见`corpora/`。完整测试与源文件核对见[主报告](../README.md)。本次有限重复未评估长期稳定性。
