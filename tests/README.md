# 提交版测试

业务验收与模块/工具/连接检查分开。`support/` 只提供共用执行与证据审计，不存放用例；提交版不导入本地归档。

保留标准：题目明确要求、与可靠问答直接相关的核心扩展、必要基础协议检查。当前49项均属于准备提交的测试（包含参数化场景，不是49个测试文件），已按当前代码完整重跑：49项通过、0失败、0错误、0跳过。4个冲突与适用关系用例另各固定执行3次，12次全部通过，不增加测试项数。保留既有查证动作与最终状态断言，并增加取证原因检查：未解冲突为conflict，明确适用关系后为sufficient；通知追问前后都为conflict，最终状态分别为needs_info和unresolved。历史导入契约还验证无原文结束被拒绝后的修正。examples保留完整回归与定向复测记录，详见[评估](../docs/03-evaluation.md)。

| 目录 | 项数 | 验证范围 |
| --- | ---: | --- |
| `e2e/required/` | 6 | 题目必验：明确答案、文档冲突、资料外问题、改写问题、上下文追问、工具失败 |
| `e2e/extended/` | 12 | 日期不消解冲突、对象澄清、部分回答、替换资料并带旧历史、读取失败、适用范围、通知转述、明确状态问题、故障恢复、用户条件更正、hybrid降级两路径 |
| `e2e/offline/` | 7 | 正式Mock BM25：正常、冲突、缺资料、工具失败、恢复、预算停止，以及不支持的输入；只证明流程 |
| `contracts/` | 24 | 配置/入口5、hybrid分支结果2、执行预算2、SDK工具调用连接1、HTTP超时/认证失败2、原文读取/引用4、块扩展章节1、会话证据复用/失效5、提交材料导出2；无真实API |

核心扩展保留的理由：日期和用户转述不能消解冲突；澄清/更正影响制度适用；部分回答需准确保留缺口；替换资料是题目审核点；两工具故障恢复和hybrid降级验证实际检索链路。基础24项由少量测试函数及其参数化场景组成，分别守住配置入口、有限执行、SDK接入、真实引用和工具协议，不保留完整开发矩阵。

默认 `python -m pytest tests -q` 不调用真实模型，18项live跳过。仅收集不能算通过。

```sh
# 基础模块／工具／连接检查
python -m pytest tests/contracts -q
# 产品Mock端到端（网络被测试主动封锁）
PYTHONPATH=src python -m knowledge_agent evaluate --mode mock --retrieval bm25 --output-dir runtime/evaluation/mock
# 真实业务，默认hybrid；加--collect-only可只收集而不调用模型
PYTHONPATH=src python -m knowledge_agent evaluate --mode real --run-live --output-dir runtime/evaluation/real
# 只跑题目必验或重要补充
PYTHONPATH=src python -m knowledge_agent evaluate --mode real --suite tests/e2e/required --run-live --output-dir runtime/evaluation/required
PYTHONPATH=src python -m knowledge_agent evaluate --mode real --suite tests/e2e/extended --run-live --output-dir runtime/evaluation/extended
```

真实业务用例始终通过产品CLI、实际框架、真实主模型和正式工具。故障由测试注入底层工具，实际错误反馈送给模型，模型自行决定恢复或停止。Mock脚本、SDK本地HTTP替身和受控排名只验证各自边界，不记为真实决策效果。

自动断言验证状态、实际执行、证据来源和连续原文；答案是否充分、忠实转述、是否多说等需要逐轮阅读。没有自然语言关键词评分器。当前实际结果、业务映射、失败与限制见[评估](../docs/03-evaluation.md)和[材料索引](../examples/README.md)。

测试断言仍读取完整运行记录。`--examples-dir` 与 `evaluate` 导出每轮输入、实际输出和精简Trace，资料快照按版本共用。精简保留失败、重试、补查、预算中断和复用证据关联；不会删掉失败测试或把受控模型计为真实模型效果。导出契约检查结果保真、原文关联、重复导出一致性和失败统计。

运行后统一打包：

```sh
PYTHONPATH=src .venv/bin/python -m knowledge_agent.submission --source runtime/evaluation/new-batch --output examples/new-submission
```

完整复跑命令和文件格式见[提交材料说明](../examples/submission-check/README.md)。运行ID与模型回答可能变化，导出结构保持一致。
