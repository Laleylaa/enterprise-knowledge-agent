# 独立检索工具实际记录

这些记录直接执行 SearchTool，stage=standalone_search_tool、model_calls=0。正常、缺资料、冲突和故障都是工具级过程，不是完整 Agent 决策／回答验收，也不计作题目要求的真实模型差异路径。

| 用例 | 输入 | 实际输出 | Trace | 效果指标 |
|---|---|---|---|---|
| 明确期限查询 | [输入](inputs/normal/739ed1cdc4fb429087b13a6149e16d07/input.json) | [输出](outputs/normal/739ed1cdc4fb429087b13a6149e16d07/output.json) | [Trace](traces/normal/739ed1cdc4fb429087b13a6149e16d07/trace.jsonl) | [核对结果](reports/normal/739ed1cdc4fb429087b13a6149e16d07/retrieval-evaluation.json) |
| 改写后的相似查询 | [输入](inputs/paraphrase/48fa32f1c2c5427d8de3cea148f26bd6/input.json) | [输出](outputs/paraphrase/48fa32f1c2c5427d8de3cea148f26bd6/output.json) | [Trace](traces/paraphrase/48fa32f1c2c5427d8de3cea148f26bd6/trace.jsonl) | [核对结果](reports/paraphrase/48fa32f1c2c5427d8de3cea148f26bd6/retrieval-evaluation.json) |
| 冲突双方召回 | [输入](inputs/conflicting_sources/89eb2183e5ad422db53f765c016f7f86/input.json) | [输出](outputs/conflicting_sources/89eb2183e5ad422db53f765c016f7f86/output.json) | [Trace](traces/conflicting_sources/89eb2183e5ad422db53f765c016f7f86/trace.jsonl) | [核对结果](reports/conflicting_sources/89eb2183e5ad422db53f765c016f7f86/retrieval-evaluation.json) |
| 育儿假资料缺口 | [输入](inputs/out_of_corpus/8063cef779984265a898a47aab9d01d3/input.json) | [输出](outputs/out_of_corpus/8063cef779984265a898a47aab9d01d3/output.json) | [Trace](traces/out_of_corpus/8063cef779984265a898a47aab9d01d3/trace.jsonl) | [核对结果](reports/out_of_corpus/8063cef779984265a898a47aab9d01d3/retrieval-evaluation.json) |
| 明确 D02 线索 | [输入](inputs/explicit_document/e4d873e9f0b14fb6a1f1b5f4a69d28a3/input.json) | [输出](outputs/explicit_document/e4d873e9f0b14fb6a1f1b5f4a69d28a3/output.json) | [Trace](traces/explicit_document/e4d873e9f0b14fb6a1f1b5f4a69d28a3/trace.jsonl) | [核对结果](reports/explicit_document/e4d873e9f0b14fb6a1f1b5f4a69d28a3/retrieval-evaluation.json) |
| 检索故障注入 | [输入](inputs/tool_failure/ef3f1f90946f42638fa96a75605c24cd/input.json) | [输出](outputs/tool_failure/ef3f1f90946f42638fa96a75605c24cd/output.json) | [Trace](traces/tool_failure/ef3f1f90946f42638fa96a75605c24cd/trace.jsonl) | [核对结果](reports/tool_failure/ef3f1f90946f42638fa96a75605c24cd/retrieval-evaluation.json) |
| 原文 30 改 20 | [输入](inputs/policy_replacement/136e603a41384ad480edd8076438a085/input.json) | [输出](outputs/policy_replacement/136e603a41384ad480edd8076438a085/output.json) | [Trace](traces/policy_replacement/136e603a41384ad480edd8076438a085/trace.jsonl) | [核对结果](reports/policy_replacement/136e603a41384ad480edd8076438a085/retrieval-evaluation.json) |

相同 case_id／run_id 关联 inputs、outputs、traces：inputs 含实际请求、corpus.json 原文／派生块快照及 index-manifest.json，故障运行另有 fault-injection.json；outputs 保存最终工具结果；traces 保存 tool-inputs.jsonl、tool-results.jsonl、observed-evidence.json、run.json、事件 Trace，以及含原始文件哈希的 artifacts.json。效果指标放 reports/<case_id>/<run_id>/。原始文件来自实际执行，预期判据只在测试代码与评估侧。

两种 F1 问法的支持条款均进入前 5，但都在第 3 位，前面的标题／用途块不能单独支持期限答案；没有把这一限制隐藏为“首位命中”。当前资料很小，不代表大规模检索效果。

自动断言报告：[业务 7 passed](reports/business/search-tool-results.xml)。整体范围与限制见 [评估文档](../../docs/03-evaluation.md)。
