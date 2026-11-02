# 方案与实现

## 调用链与职责

CLI接收问题及可选历史 → 加载Markdown原文与版本快照 → 真实模型选择search_knowledge或read_document → 工具返回原文及执行状态 → 模型观察并决定补充检索、读取、追问或submit_answer。证据充分即可结束，不强制最少搜索次数或重复读取。

主模型使用OpenAI兼容SDK接入；PydanticAI **2.64.0** 承担Agent循环、工具注册、参数校验与结果校验调度；OpenAI SDK **3.42.0** 承担HTTP协议。业务代码承担资料、检索、读取、证据登记、预算、会话和记录。没有自建多Agent或生产Runtime。依赖版本见requirements.txt。

## 资料和检索

原文为 `data/fixtures/*/documents/*.md`，manifest记录文档ID、标题、版本日期。预生成块位于data/prepared，保存文档/章节/块定位、精确字符范围和内容哈希。不可将向量相似度、文档标题或定位对象当成制度依据。

prepare按Markdown结构和固定tokenizer分块，复用输入快照；内容变更需重新准备。BM25使用jieba与rank-bm25；向量为本地固定版本BGE，CPU工作进程可取消。hybrid在同一快照上融合两分支排名，使用等权RRF（k=60），不混合不同量纲的原始分数。小型资料采用精确检索，无外部向量库。

真实入口默认hybrid，可显式BM25/vector；Mock仅BM25。hybrid分支失败时保留另一分支真实结果，以partial、errors及effective_branches说明。仅当现有原文不足且故障阻断必要查证时，回答才应incomplete。partial不自动意味着资料无效。初始化与查询错误、分支执行情况均可从Trace核实。

## 工具与证据

- search_knowledge：query、purpose、可选doc_ids、limit和cursor；返回原文块及文档/章节定位。精确ID定位不依赖向量排序。
- read_document：doc_id和purpose；可选section_id或chunk_id及cursor。只传doc_id读全文，section_id读章节，chunk_id仅该块。过大内容返回可继续读取的locators，定位信息本身不是正文证据。
- 两工具共享当前轮快照、EvidenceStore及调用ID。引用必须指向本轮已送达模型的evidence_id、正确doc_id及连续原文；不能拼接分离标题与正文，也不能引用历史轮次证据。

这些程序检查证明来源真实性，不证明自然语言结论一定得到引文支持；后者仍需模型判断和实际输出审阅。

## 决策与最终答复

prompts.py分开维护服务定位、当前问题理解、证据审查、输出规则和少量表达示例；工具使用细节放在工具介绍。每次观察后判断：是否覆盖所问、适用范围与关键条件是否明确、是否有未解冲突。缺上下文继续取证，缺用户条件则追问，合理查证仍无依据则停止。

文档冲突时查证范围/替代关系，不按日期新旧、数值大小或用户转述自行定优先级。用户没有更多可核实线索时保留冲突，不循环追问。未能核实只说明本轮取证局限，不断言信息本身无效。明确适用范围后只交付当前场景所需规则。

最终结构为answer、citations（evidence_id/doc_id/quote）、gaps、status，以及clarification和简短decision_summary：

| 状态 | 含义 |
| --- | --- |
| resolved | 本轮所问均有依据，引用支持结论，gaps为空 |
| needs_info | 需用户补充具体条件或线索，提供clarification |
| unresolved | 合理查证仍缺依据或冲突未解，无进一步追问 |
| incomplete | 必要处理被故障或执行上限阻断 |

有部分证据时保留有依据的部分答案，不把资料缺失伪装成工具故障。工具调用与submit_answer分开，先观察再结束；不要求或存储模型内部思维过程。

## 会话、上限与Mock

每轮新建run_id、证据与预算，session_id/turn_id/previous_run_id串联会话。历史仅传公开用户文本与最终答复，不携带旧工具观察作为本轮证据；支持条件更正及显式历史导入。退出清空运行时历史，重启不自动加载Trace。

模型轮数、HTTP尝试、工具调用及总时间均有上限。达到限制返回incomplete及termination_reason，不继续无限执行；格式修正和传输重试有独立有限额度，不把自动重试视为模型动态决策。

Mock使用产品内固定场景脚本，BM25、读取和预算守卫实际执行，禁止真实模型请求。不支持输入明确拒绝，输出标注mode/mock_scenario/result_origin。真实服务失败不切Mock。

## 验证与材料组织

提交版 `tests/e2e/required` 覆盖六类题目必验；`extended` 为重要补充；`offline` 为产品Mock；`contracts` 验证少量基础模块/工具/SDK连接，受控替身不计真实效果。

evaluate的real默认选择required与extended，mock只选择offline；每次生成独立批次。归档保持 inputs/outputs/traces/reports 同case_id/run_id，artifacts.json关联原始文件SHA-256。模型请求、工具参数、实际返回、后续动作及purpose/decision_summary可复核。业务语义阅读单列，不用自动绿灯代替。

测试分层与运行命令见[测试说明](../tests/README.md)，全部验收点和实际路径见[评估](03-evaluation.md)。完整开发测试和历史批次移入Git忽略的local_validation，提交版可在没有该目录的副本中独立运行。

## 取舍与限制

本项目选择CLI、小型合成知识库与本地工具，聚焦决策、引用和故障处理。hybrid增加本地模型资产及进程管理成本，BM25仍作为显式低依赖入口及降级分支。未实现权限控制、在线文档同步、服务化部署或大库性能验证；不将考核Demo表述为生产系统。
