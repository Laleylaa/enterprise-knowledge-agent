# 本批真实模型决策路径

下面路径均来自本次真实模型调用。工具故障由测试注入，后续动作由模型决定；不是预设决策日志。每条路径附原始记录，参数和错误详情可复核。

## required_clear_answer

问题：国内差旅报销期限多久？

| 模型轮次 | 动作及参数 | 实际返回摘要 | 本次动作目的 |
| --- | --- | --- | --- |
| 1 | search_knowledge `{"query": "国内差旅费报销期限"}` | ok；4条原文；文档：D01 | 查找国内差旅报销时限条款 |

取证停止：sufficient。D01《差旅报销规定》国内差旅报销规定明确：国内差旅报销须在行程结束后30天内提交，已覆盖所问期限及起算条件。

后续回答：resolved。期限及行程结束后的起算条件准确，引用D01。

[原始输入](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/inputs/required_clear_answer/8524943db15a4b3081d4ca21ed279726/input.json) · [原始Trace](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/traces/required_clear_answer/8524943db15a4b3081d4ca21ed279726/trace.jsonl) · [实际输出](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/required_clear_answer/8524943db15a4b3081d4ca21ed279726/output.json)

## required_conflict

问题：差旅报销期限多久？

| 模型轮次 | 动作及参数 | 实际返回摘要 | 本次动作目的 |
| --- | --- | --- | --- |
| 1 | search_knowledge `{"query": "差旅报销期限"}` | ok；4条原文；文档：D01,D02 | 查找差旅费用报销的时限规定 |
| 2 | read_document `{"doc_id": "D01"}` | ok；2条原文；文档：D01 | 核实 D01 的适用范围与是否说明替代关系 |
| 2 | read_document `{"doc_id": "D02"}` | ok；2条原文；文档：D02 | 核实 D02 的适用范围与是否说明替代关系 |

取证停止：missing。已检索并完整读取两份《差旅报销规定》(D01 为 30 天、D02 为 15 天，同为 2026-01-01 版)；两文均无适用范围说明，也无替代/废止关系，无法判定哪份适用于用户。已无其他可查线索，故以缺依据结束，冲突双方原文一并交付。

后续回答：needs_info。检索发现双方后读取两份原文查证，保留30天/15天并追问适用依据。

[原始输入](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/inputs/required_conflict/73186d3f358747f79d7328866b8db26c/input.json) · [原始Trace](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/traces/required_conflict/73186d3f358747f79d7328866b8db26c/trace.jsonl) · [实际输出](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/required_conflict/73186d3f358747f79d7328866b8db26c/output.json)

## extended_read_failure

问题：请读取 D01 原文，核实国内差旅报销期限。

| 模型轮次 | 动作及参数 | 实际返回摘要 | 本次动作目的 |
| --- | --- | --- | --- |
| 1 | read_document `{"doc_id": "D01"}` | error；0条原文；文档：；错误：READ_FAILED | 读取 D01 全文以核实国内差旅报销期限条款 |
| 2 | read_document `{"doc_id": "D01"}` | error；0条原文；文档：；错误：READ_FAILED | 重试读取 D01 全文，取得国内差旅报销期限原文 |
| 3 | search_knowledge `{"query": "国内差旅报销期限", "doc_ids": ["D01"], "limit": 10}` | ok；4条原文；文档：D01 | 全文读取失败，改用检索取得国内差旅报销期限相关原文 |

取证停止：sufficient。D01 全文读取两次均报 READ_FAILED，改用限定 D01 的检索成功取得其各章节原文，已覆盖“提交期限”条款（行程结束后 30 天内提交）及适用范围说明，足以核实国内差旅报销期限。

后续回答：resolved。读取两次失败后改用搜索，期限结论与引用正确。附带分别记录的原文，未推导期限不受状态影响；decision_summary称直接读取到原文，实际取得途径以Trace中的搜索为准。

[原始输入](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/inputs/extended_read_failure/74eff099f8dd47a8b772db545ded8ee7/input.json) · [原始Trace](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/traces/extended_read_failure/74eff099f8dd47a8b772db545ded8ee7/trace.jsonl) · [实际输出](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/extended_read_failure/74eff099f8dd47a8b772db545ded8ee7/output.json)

## required_tool_failure

问题：国内差旅报销期限多久？

| 模型轮次 | 动作及参数 | 实际返回摘要 | 本次动作目的 |
| --- | --- | --- | --- |
| 1 | search_knowledge `{"query": "国内差旅报销期限"}` | error；0条原文；文档：；错误：SEARCH_FAILED | 查找国内差旅费用报销的时间期限规定 |
| 2 | search_knowledge `{"query": "差旅费报销 时限 天数 期限"}` | error；0条原文；文档：；错误：SEARCH_FAILED | 检索失败后重试，查找差旅报销期限规定 |
| 3 | search_knowledge `{"query": "差旅费管理办法"}` | error；0条原文；文档：；错误：SEARCH_FAILED | 再次尝试以更宽泛查询获取差旅制度原文，确认是否为服务故障 |

取证停止：blocked。问题对象明确（国内差旅报销期限），但连续三次检索的 BM25 与向量分支均执行失败，未取得任何原文，无法核实期限条款；属工具故障阻断必要查证，非资料缺失。

后续回答：incomplete。三次检索全分支失败后blocked，模型回答incomplete，无伪造引用或重复追问。

[原始输入](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/inputs/required_tool_failure/9a6f8e550b4b4b298b46b3cbe9d56f90/input.json) · [原始Trace](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/traces/required_tool_failure/9a6f8e550b4b4b298b46b3cbe9d56f90/trace.jsonl) · [实际输出](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/required_tool_failure/9a6f8e550b4b4b298b46b3cbe9d56f90/output.json)
