# 真实模型的不同执行路径

下列摘要由本批原始记录提取；工具参数及返回全文在对应Trace。所有后续动作由真实主模型选择，故障注入只改变工具后端。

## required_clear_answer

[实际输出](artifacts/e2e/outputs/required_clear_answer/d27324d1dc574e619e7d226388810ba5/output.json) / [输入](artifacts/e2e/inputs/required_clear_answer/d27324d1dc574e619e7d226388810ba5/input.json)

| 模型轮次 / 工具 | 参数 | 返回摘要 | 行动依据 |
| --- | --- | --- | --- |
| 1 / search_knowledge | `{"query": "国内差旅报销期限", "purpose": "查找国内差旅报销提交期限规定", "doc_ids": null, "limit": 5, "cursor": null}` | ok; 文档=D01; 错误=无 | 查找国内差旅报销提交期限规定 |

最终动作：submit_answer → resolved。简要依据：依据差旅报销规定 D01 提交期限条款作答。

## required_conflict

[实际输出](artifacts/e2e/outputs/required_conflict/37277fc358e944d8b21a4b091f12c7ba/output.json) / [输入](artifacts/e2e/inputs/required_conflict/37277fc358e944d8b21a4b091f12c7ba/input.json)

| 模型轮次 / 工具 | 参数 | 返回摘要 | 行动依据 |
| --- | --- | --- | --- |
| 1 / search_knowledge | `{"query": "差旅报销期限", "purpose": "查找差旅报销提交期限规定", "doc_ids": null, "limit": 5, "cursor": null}` | ok; 文档=D01,D02; 错误=无 | 查找差旅报销提交期限规定 |
| 2 / read_document | `{"doc_id": "D01", "purpose": "核实 D01 的适用范围与是否有其他条款", "section_id": null, "chunk_id": null, "cursor": null}` | ok; 文档=D01; 错误=无 | 核实 D01 的适用范围与是否有其他条款 |
| 2 / read_document | `{"doc_id": "D02", "purpose": "核实 D02 的适用范围与是否有其他条款", "section_id": null, "chunk_id": null, "cursor": null}` | ok; 文档=D02; 错误=无 | 核实 D02 的适用范围与是否有其他条款 |

最终动作：submit_answer → needs_info。简要依据：两份差旅报销规定给出不同期限且无适用范围，需询问适用制度或可核实线索。

## required_missing

[实际输出](artifacts/e2e/outputs/required_missing/9e4305261c134c9fbe37beb3f515297e/output.json) / [输入](artifacts/e2e/inputs/required_missing/9e4305261c134c9fbe37beb3f515297e/input.json)

| 模型轮次 / 工具 | 参数 | 返回摘要 | 行动依据 |
| --- | --- | --- | --- |
| 1 / search_knowledge | `{"query": "育儿假 天数", "purpose": "查找公司育儿假天数规定", "doc_ids": null, "limit": 5, "cursor": null}` | ok; 文档=D01,D02,D04; 错误=无 | 查找公司育儿假天数规定 |
| 2 / search_knowledge | `{"query": "育儿假 子女 假期天数 生育", "purpose": "再次检索育儿假相关条款", "doc_ids": null, "limit": 5, "cursor": null}` | ok; 文档=D01,D02,D04; 错误=无 | 再次检索育儿假相关条款 |
| 3 / read_document | `{"doc_id": "D04", "purpose": "确认请假规定是否含育儿假条款", "section_id": null, "chunk_id": null, "cursor": null}` | ok; 文档=D04; 错误=无 | 确认请假规定是否含育儿假条款 |

最终动作：submit_answer → unresolved。简要依据：检索育儿假相关条款仅得到差旅报销和请假申请流程内容，请假规定全文也无育儿假条款，故无法确定天数。

## extended_read_failure

[实际输出](artifacts/e2e/outputs/extended_read_failure/b82f9bfc169d4fcab3db8bd5e7be9d2a/output.json) / [输入](artifacts/e2e/inputs/extended_read_failure/b82f9bfc169d4fcab3db8bd5e7be9d2a/input.json)

| 模型轮次 / 工具 | 参数 | 返回摘要 | 行动依据 |
| --- | --- | --- | --- |
| 1 / read_document | `{"doc_id": "D01", "purpose": "读取 D01 全文核实国内差旅报销期限", "section_id": null, "chunk_id": null, "cursor": null}` | error; 文档=无; 错误=READ_FAILED | 读取 D01 全文核实国内差旅报销期限 |
| 2 / read_document | `{"doc_id": "D01", "purpose": "重试读取 D01 全文", "section_id": null, "chunk_id": null, "cursor": null}` | error; 文档=无; 错误=READ_FAILED | 重试读取 D01 全文 |
| 3 / search_knowledge | `{"query": "国内差旅报销期限", "purpose": "全文读取失败，改用检索尝试取得 D01 相关原文", "doc_ids": ["D01"], "limit": 10, "cursor": null}` | ok; 文档=D01; 错误=无 | 全文读取失败，改用检索尝试取得 D01 相关原文 |

最终动作：submit_answer → resolved。简要依据：全文读取失败，改按 doc_ids 检索 D01，取得“二、提交期限”整节原文，覆盖国内差旅报销期限及起算条件。

## extended_recovery

[实际输出](artifacts/e2e/outputs/extended_recovery/2a2de31ace564c4985fde230ec981f4a/output.json) / [输入](artifacts/e2e/inputs/extended_recovery/2a2de31ace564c4985fde230ec981f4a/input.json)

| 模型轮次 / 工具 | 参数 | 返回摘要 | 行动依据 |
| --- | --- | --- | --- |
| 1 / search_knowledge | `{"query": "国内差旅报销提交期限", "purpose": "查找国内差旅报销期限规定", "doc_ids": null, "limit": 5, "cursor": null}` | error; 文档=无; 错误=SEARCH_FAILED,SEARCH_FAILED | 查找国内差旅报销期限规定 |
| 2 / search_knowledge | `{"query": "差旅报销 期限 天内提交", "purpose": "重试检索国内差旅报销期限规定", "doc_ids": null, "limit": 5, "cursor": null}` | ok; 文档=D01; 错误=无 | 重试检索国内差旅报销期限规定 |

最终动作：submit_answer → resolved。简要依据：检索到《差旅报销规定 D01》提交期限条款，直接据此答复国内差旅报销期限。

## hybrid_partial_sufficient

[实际输出](artifacts/e2e/outputs/hybrid_partial_sufficient/db2ac0181b7f4afc9370d071385c5616/output.json) / [输入](artifacts/e2e/inputs/hybrid_partial_sufficient/db2ac0181b7f4afc9370d071385c5616/input.json)

| 模型轮次 / 工具 | 参数 | 返回摘要 | 行动依据 |
| --- | --- | --- | --- |
| 1 / search_knowledge | `{"query": "国内差旅报销期限", "purpose": "查找国内差旅报销的提交期限规定", "doc_ids": null, "limit": 5, "cursor": null}` | partial; 文档=D01; 错误=EMBEDDING_TIMEOUT | 查找国内差旅报销的提交期限规定 |

最终动作：submit_answer → resolved。简要依据：检索到 D01《差旅报销规定》提交期限条款，直接回答国内差旅报销期限。

## hybrid_partial_section_context

[实际输出](artifacts/e2e/outputs/hybrid_partial_section_context/859fc5bf5f8347b38f2e24c93d680452/output.json) / [输入](artifacts/e2e/inputs/hybrid_partial_section_context/859fc5bf5f8347b38f2e24c93d680452/input.json)

| 模型轮次 / 工具 | 参数 | 返回摘要 | 行动依据 |
| --- | --- | --- | --- |
| 1 / search_knowledge | `{"query": "草稿保存时间", "purpose": "检索草稿保存时间片段", "doc_ids": null, "limit": 3, "cursor": null}` | partial; 文档=D10; 错误=EMBEDDING_TIMEOUT | 检索草稿保存时间片段 |
| 1 / search_knowledge | `{"query": "海外差旅报销 行程结束后30天内提交", "purpose": "核实海外差旅提交期限", "doc_ids": null, "limit": 5, "cursor": null}` | partial; 文档=D10; 错误=EMBEDDING_TIMEOUT | 核实海外差旅提交期限 |

最终动作：submit_answer → unresolved。简要依据：已取得草稿保存时间条款，并据适用范围条款确认海外差旅期限不在本节，未找到对应制度，故海外期限部分未解决。
