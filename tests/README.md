# 提交版测试

业务验收与模块/工具/连接检查分开。`support/` 只提供共用执行与证据审计，不存放用例；提交版不导入本地归档。

| 目录 | 项数 | 验证范围 |
| --- | ---: | --- |
| `e2e/required/` | 6 | 题目必验：明确答案、文档冲突、资料外问题、改写问题、上下文追问、工具失败 |
| `e2e/extended/` | 12 | 日期不消解冲突、对象澄清、部分回答、替换资料并带旧历史、读取失败、适用范围、通知转述、明确状态问题、故障恢复、用户条件更正、hybrid降级两路径 |
| `e2e/offline/` | 7 | 正式Mock BM25：正常、冲突、缺资料、工具失败、恢复、预算停止，以及不支持的输入；只证明流程 |
| `contracts/` | 17 | 配置/入口5、hybrid分支结果2、执行预算2、SDK工具调用连接1、HTTP超时/认证失败2、原文读取/引用4、块扩展章节1；无真实API |

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

历史完整开发回归、重复参数矩阵及诊断材料放在 Git 忽略的 `local_validation/tests/`、`local_validation/examples/`，用 `.venv/bin/python local_validation/run_tests.py` 运行。它们不是提交版依赖。
