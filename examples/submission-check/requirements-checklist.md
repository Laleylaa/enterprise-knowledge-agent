# 题目逐项对照

审核日期：2026-11-02。以本批冻结代码、现有提交测试和实际输出为依据。自动测试42/42通过；业务正确性、展示质量与提交完成度分别判断。

## 业务实现与Agent决策

| 要求 | 当前证据 | 判断 |
| --- | --- | --- |
| 员工可靠查询制度或产品问题 | 本项目选择员工制度，符合题目范围 | 已实现 |
| 问题及可选历史 | CLI支持单轮、连续对话及history导入；上下文与更正用例实际执行 | 已实现并验证 |
| 合成FAQ/制度有文档ID和版本日期 | knowledge_base与fixtures均有manifest及正文 | 已完成 |
| 文档检索工具 | search_knowledge，支持BM25/向量/RRF hybrid，返回真实片段 | 已实现并验证 |
| 片段读取工具 | read_document支持全文、章节、块及分页 | 已实现；三种读取模式契约测试通过 |
| 回答、文档ID和原文引用、缺口、状态 | JSON和文本展示具备四类内容；真实引用由程序展开 | 已实现；另有一处正文内部ID展示问题 |
| 模型选择动作、工具执行、观察后调整或结束 | 正常、冲突、读取故障恢复等真实路径见[决策记录](decision-paths.md) | 已满足 |
| 不能以固定条件/自动重试冒充ReAct | 真实用例调用实际服务；仅故障由测试注入，模型自行决定动作；Mock明确分开 | 已满足 |
| 至少两条不同执行路径 | 检索充分后结束；冲突后读取双方；读取故障后改搜索 | 已满足，超过两条 |
| 步骤、工具参数、返回、后续动作、简要依据 | 模型请求、tool_requested/tool_result、purpose及decision_summary完整保存 | 已满足；个别过程摘要表述不精确，以原始工具Trace为准 |
| 执行上限及明确未完成 | 模型/工具预算契约两项通过；Mock预算端到端返回incomplete | 已满足，Mock不当作真实决策证据 |
| 冲突说明并查证，不擅选 | 必验冲突和较新日期反例都实际读取双方，列出30天/15天并追问 | 已验证 |
| 替换资料后答案/动作响应新结果 | 带旧历史，重新检索替换资料后答20天；原先答30天 | 已验证 |
| 引用原文支持回答 | 逐轮阅读23份输出、27条引用，未发现本批无依据政策结论或错误来源引用 | 本批观察满足；非通用语义保证 |

## 六类必须验收

各项的原始输入、实际输出、Trace链接见[逐轮审核](output-review.md)。

| 场景 | 现有测试 | 实际结果 | 判断 |
| --- | --- | --- | --- |
| 明确答案 | required/test_acceptance.py::test_clear_answer | 行程结束后30天内，引用D01 | 通过 |
| 文档冲突 | required/test_acceptance.py::test_conflicting_documents | 查证双方，保留30天/15天并追问 | 通过 |
| 资料外问题 | required/test_acceptance.py::test_outside_material | 不编造育儿假天数，明确缺依据 | 通过 |
| 改写相似问题 | required/test_acceptance.py::test_paraphrased_question | 两种问法结论及起算条件一致 | 通过 |
| 上下文追问 | required/test_acceptance.py::test_context_followup | 期限呢正确承接国内差旅并重新取证 | 业务通过；首轮另有内部ID显示问题 |
| 工具失败 | required/test_acceptance.py::test_tool_failure | 三次全分支故障后blocked→incomplete，无伪造引文 | 通过 |

## 运行与仓库交付

| 要求 | 当前证据 | 判断 |
| --- | --- | --- |
| CLI/API/Notebook任选一，有可复制运行步骤 | CLI；README提供安装、离线、真实、测试命令 | 已提供；本批在已有依赖环境运行 |
| 离线Mock入口及边界 | 7项离线测试通过；固定脚本标注mode/scenario/origin，文本状态注明边界 | 已满足 |
| README环境、安装、运行、评审入口 | 仓库README齐全并指向评估材料 | 已提供 |
| src、tests、examples、data | 均存在；现有42项完整执行，真实23轮、Mock6轮有原始记录 | 已提供 |
| 至少3组正常、信息不足、故障输入输出Trace | 本批正常、缺资料、冲突、故障均有记录 | 已满足 |
| 需求文档 | docs/01-requirements.md | 已提供 |
| 方案及框架版本/职责 | docs/02-solution.md，PydanticAI 2.64.0及SDK职责有说明 | 已提供 |
| 评估预期、实际、失败和限制，引用对应文件 | docs/03-evaluation.md及本批报告、逐轮审核 | 已提供 |
| AI辅助范围、个人修改与验证 | docs/04-ai-usage.md记录AI工作与验证，个人贡献需本人确认 | 待本人核实完成 |
| 复盘：难点、学习、下一步 | docs/05-retrospective.md仍为待本人核实草稿 | 待本人核实完成 |
| 依赖与.env.example | requirements.txt、pyproject.toml及变量示例齐全 | 已提供 |
| 记录实际用时与未完成部分 | 未完成项已记录；实际个人投入时长未填写 | 未完全完成 |
| 题号、GitHub URL、最终commit SHA | 正式题号和最终SHA待填；本次未commit/push | 未完成 |
| 私有仓库指定评审可读 | 未核验远程可见性/账号访问 | 待确认 |
| 不提交真实密钥/隐私；材料同仓库 | 当前API密钥未出现在候选提交文件；.env、runtime和local_validation未跟踪，材料在同仓库 | 当前检查通过；非全历史秘密/隐私审计 |
| 非提交诊断放local并忽略 | local_validation命中忽略，无被跟踪文件，提交代码无导入依赖 | 已核对 |

## 用户新增展示要求

默认渲染只组织任务状态、回答（含追问）、引用和缺口；旧的completed诊断行、运行路径、字符位置等不再输出。但本批首轮上下文回答自身包含source_id，渲染后依然可见，故该批次“内部执行信息仅留JSON/Trace”未完全满足。见[实际输出](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/required_context/3c428cbd87584320a61313b6f01c67bc/output.json)。没有新增断言来掩盖自动测试覆盖边界，也没有将此问题夸大为制度答案错误。后续修订与定向复测见[修订报告](../source-id-boundary/README.md)。

题目不要求网页、部署、多Agent或生产Runtime；未做这些不算缺项。也不要求为本次审核新增测试、查询扩写或reranker。
