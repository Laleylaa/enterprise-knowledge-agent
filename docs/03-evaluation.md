# 开发评估记录

记录日期：2026-11-01。当前维护接入底座、主循环基线及独立检索／读取工具验证，不代表 PRD 业务验收通过。

## 环境

macOS arm64；Python 3.11.15；PydanticAI 2.64.0；Pydantic 2.14.2；OpenAI SDK 3.42.0；pydantic-settings 2.16.2；pytest 9.2.0。完整版本统一保存在 `requirements.txt`。

安装时首次受网络沙箱限制失败；获得联网授权后安装成功。`pip check` 无依赖冲突，项目可编辑安装成功。

## 冒烟预期与实际结果

初始阶段命令（使用整理后的目录；当前范围调整后的结果见下文）：`python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/smoke-results.xml`。历史报告及运行材料已迁入 `examples/integration/`，原文件内容未改写。

实际：**5 passed，1 skipped**。机器记录：[smoke-results.xml](../examples/integration/reports/smoke/smoke-results.xml)。

| 检查 | 预期 | 实际 |
|---|---|---|
| Python 模块入口 | 帮助正常显示、退出码 0 | 通过 |
| 配置入口 | CLI > 环境 > .env；不输出测试密钥 | 通过 |
| 无网络离线端到端 | 实际执行工具、反馈结果、校验引用、保存材料 | 通过；2 次脚本决策、1 次工具、0 次 HTTP |
| 缺少真实密钥 | mode 保留 real，未完成，不自动 Mock | 通过；missing_api_key，0 次 HTTP |
| 非法预算配置 | 在调用模型或工具前报配置错误 | 通过 |
| 真实模型工具闭环 | 真实模型选择工具并观察后提交结构化结果 | 默认执行仍跳过；配置密钥后显式执行，联网运行 1 项通过，详见下文 |

离线测试在移除配置密钥、禁止真实模型请求并封锁 socket 连接／域名解析的情况下执行。其来源仍为预设脚本，不作为真实 ReAct 成绩。

## 开发冒烟的输入、输出与调试记录

- 离线运行：[输入](../examples/integration/inputs/cli_mock/7882cbd51ad8437e9901d74fa081be6b/input.json)、[工具结果](../examples/integration/traces/cli_mock/7882cbd51ad8437e9901d74fa081be6b/tool-results.jsonl)、[实际模型适配层输入](../examples/integration/traces/cli_mock/7882cbd51ad8437e9901d74fa081be6b/model-inputs.jsonl)、[Trace](../examples/integration/traces/cli_mock/7882cbd51ad8437e9901d74fa081be6b/trace.jsonl)、[输出](../examples/integration/outputs/cli_mock/7882cbd51ad8437e9901d74fa081be6b/output.json)。
- 真实模式启动：[输入](../examples/integration/inputs/cli_real/b31b71e307f14fbe980e1843cb1f7712/input.json)、[Trace](../examples/integration/traces/cli_real/b31b71e307f14fbe980e1843cb1f7712/trace.jsonl)、[输出](../examples/integration/outputs/cli_real/b31b71e307f14fbe980e1843cb1f7712/output.json)。缺少密钥，退出码 1，没有调用真实服务。这是配置中断记录，不是 DeepSeek 服务故障或模型决策证据。

每次实际模型／脚本响应保存在 Trace 的 model_response 事件；每次请求的公开消息、工具定义与指令保存在 model-inputs.jsonl。没有后续模型调用时不补造观察或决策。

## 真实模型冒烟补充记录

2026-11-01 用户在本机配置密钥后显式执行真实冒烟；没有修改业务代码或测试判据。

1. 首次在受限环境中运行，模型连接失败，有限重试后以 incomplete 结束：[失败测试报告](../examples/integration/reports/smoke/live-smoke-results.xml)、[实际 Trace](../examples/integration/traces/cli_real/1f55c124a9804f9fb26850da0fd27fb4/trace.jsonl)。2 次请求尝试均为 ModelConnectionError，未取得模型响应；不归因为模型语义错误。
2. 获得联网授权后运行同一测试，**1 passed in 5.57s**：[测试报告](../examples/integration/reports/smoke/live-smoke-network-results.xml)、[实际输入](../examples/integration/inputs/cli_real/2f49173f9b8540b8af130a1e735b8430/input.json)、[Trace](../examples/integration/traces/cli_real/2f49173f9b8540b8af130a1e735b8430/trace.jsonl)、[输出](../examples/integration/outputs/cli_real/2f49173f9b8540b8af130a1e735b8430/output.json)。

成功运行使用 deepseek-flash，整轮约 5.16 秒，4 次模型决策／HTTP 尝试、2 次业务工具调用。实际顺序为 search_knowledge → read_document → 首次结构化输出校验未通过 → 模型修正并结束。首个候选同时声明 resolved 和非空 gaps，被字段约束拒绝；模型收到反馈后，移除未被当前问题要求的延伸事项，最终回答“国内差旅报销须在行程结束后 30 天内提交”，引用 D01 对应原文，状态 resolved。AI 辅助核对本例最终条件、期限及引文与资料一致；尚不代表用户已完成人工验收。

两次运行分别记录为受限网络失败和联网成功，不隐藏首次失败，也不据单次成功宣称稳定性或完整契约通过。此前缺少密钥的记录继续保留为历史结果。

## 业务流程验证材料状态

`examples/e2e/` 保存后续完整业务验收材料，按 inputs、outputs、traces、reports 分类，以相同用例／运行 ID 配对。当前只有规范说明，完整验收尚未执行。模块测试与接入冒烟也可拥有 Trace，分别归对应模块和 integration。

上述开发冒烟材料统一归 `examples/integration/`，只能证明当前检查范围内的程序链路；不能把缺少密钥或模型连接失败当作业务工具失败场景，也不能用已有文件组数代替至少三类业务场景与全部验收点的覆盖。后续本评估文档分别引用业务流程证据和开发测试报告。

目录整理后复跑默认冒烟，结果为 **5 passed，1 skipped**，见 [整理后报告](../examples/integration/reports/smoke/organization-smoke-results.xml)。另核对默认 CLI 试跑写入被忽略的 runtime/runs，文档链接均有效；没有为本次目录调整重新调用真实 API。迁移的 28 个历史证据文件逐个核对内容哈希一致。

## 历史测试范围调整

资料准备阶段曾提前生成全量用例规格、旧格式草稿及静态检查，后来又增加独立加载边界检查。这些与当前开发阶段不匹配，现按用户要求移除；Q01～Q18 的验收要求仍保留在 solution，随实际功能逐项实现。源数据契约继续使用 manifest＋独立 Markdown，F1 原文样例保留。

历史实际报告原样保留：[静态目录检查 3 passed](../examples/integration/reports/smoke/case-catalog-results.xml)、[当时回归 8 passed／1 skipped](../examples/integration/reports/smoke/data-baseline-smoke-results.xml)、[加载检查阶段 16 passed／1 skipped](../examples/integration/reports/smoke/document-source-smoke-results.xml)。这些报告反映当时的测试集合，不是当前测试清单，也不证明业务验收完成；其中已移除的测试不可再按旧命令复现。

## 当前冒烟范围

冒烟部分保留 tests/integration/smoke/test_cli.py 与 test_live.py。新存储契约的最小检查已并入原有离线端到端：从 manifest 指向的 Markdown 读取原文，核对实际运行的资料快照、工具证据及引用一致。独立组件的完整契约与业务测试后续按功能进度补充。

本次实际结果：**5 passed，1 skipped in 0.85s**，见 [当前范围冒烟报告](../examples/integration/reports/smoke/scope-aligned-smoke-results.xml)。跳过项为需显式启用的真实 API 冒烟；本次没有真实 API 请求。

```sh
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/scope-aligned-smoke-results.xml
```

## 主循环第 1 步：正常继续与结束

PydanticAI 继续负责模型请求、工具分发与回到模型的循环；应用未另写固定步骤循环。run_turn 新增可选模型工厂注入点，默认仍使用原有真实／Mock 接入。契约测试仅替换模型响应，复用实际本地工具、证据登记、输出校验及记录路径；指令明确允许无需取证的直接澄清。

| 用例 | 预期 | 实际 |
|---|---|---|
| search_then_finish | 实际检索结果进入下次请求，终态使用返回的证据身份及原文；之后不再调用模型／工具 | 通过 |
| search_read_then_finish | 依据检索返回的文档 ID 继续读取，原文进入下次请求，再独立结束 | 通过 |
| clarification_can_finish_without_tools | 合法 needs_info 直接结束；一次模型响应、零工具、无虚构证据或工具记录 | 通过 |

代码：[test_normal_flow.py](../tests/agent_loop/contract/test_normal_flow.py)。使用显式命名的 FunctionModel 脚本，mode=mock，禁用真实请求和网络，不读取本地密钥。工具仍为 smoke_fixture，小型资料全集返回，不证明检索效果或模型语义能力。以上只验证正常控制流；未覆盖混合响应、错误修正、预算精确边界、重试、超时及取消。

实际契约结果 **3 passed in 0.47s**：[契约报告](../examples/agent_loop/reports/contract/agent-loop-normal-results.xml)。原有冒烟回归 **5 passed，1 skipped in 0.86s**：[冒烟报告](../examples/integration/reports/smoke/agent-loop-normal-smoke-results.xml)。跳过真实 API 项，本步无真实模型调用、无业务验收 Trace。运行中输入／输出／工具记录保存在 pytest 临时目录，检查实际记录与模型请求的一致性；长期保留上述报告。

```sh
python -m pytest tests/agent_loop/contract/test_normal_flow.py -q --junitxml=examples/agent_loop/reports/contract/agent-loop-normal-results.xml
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/agent-loop-normal-smoke-results.xml
```

## 主循环第 2 步：输出校验与修正

仅新增 [test_output_correction.py](../tests/agent_loop/contract/test_output_correction.py)，受控模型响应经过同一 PydanticAI 循环与本地工具。未新增知识资料、检索实现或业务验收用例。

| 检查组 | 用例数 | 实际 |
|---|---:|---|
| 缺字段／非法 JSON 的结构错误，收到反馈后修正 | 2 | 通过 |
| 非本轮证据 ID、错误文档 ID、篡改引文，收到反馈后修正 | 3 | 通过 |
| 混合响应：工具先／终态先 × 合法／非法结构；拒绝同批终态，工具与拒绝原因进入下一次请求 | 4 | 通过 |
| 连续两次混合后：第三次合法终态可结束；第三次仍混合则工具不执行 | 2 | 通过 |
| 修正额度为零时，混合响应在执行工具前停止 | 1 | 通过 |
| 结构错误→工具成功→引用错误→混合响应，共享额度不重置 | 1 | 通过 |
| 结构错误→混合响应→最后一次合法修正 | 1 | 通过 |
| 连续结构错误／连续引用错误耗尽额度，不再追加总结调用 | 2 | 通过 |

输出修正契约 **16 passed in 0.37s**：[报告](../examples/agent_loop/reports/contract/agent-loop-output-correction-results.xml)。第 1 步回归 **3 passed in 0.23s**：[正常路径报告](../examples/agent_loop/reports/contract/agent-loop-normal-regression-results.xml)。冒烟回归 **5 passed，1 skipped in 0.84s**：[冒烟报告](../examples/integration/reports/smoke/output-correction-smoke-results.xml)。无真实 API 调用；测试中的模型修正是脚本行为，不证明真实模型会修正成功。

结构解析和反馈交给框架，应用钩子维护跨错误类型的输出修正额度。混合响应在交给框架执行前检查额度，避免 graceful 执行顺序让第三批工具先跑。额度耗尽以 output_retry_limit／incomplete 中断，已有原文仍由运行结果保留。测试核对实际下一次请求中的反馈、工具记录和终止次数，临时过程文件不作为业务验收 Trace。

```sh
python -m pytest tests/agent_loop/contract/test_output_correction.py -q --junitxml=examples/agent_loop/reports/contract/agent-loop-output-correction-results.xml
python -m pytest tests/agent_loop/contract/test_normal_flow.py -q --junitxml=examples/agent_loop/reports/contract/agent-loop-normal-regression-results.xml
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/output-correction-smoke-results.xml
```

第 2 步结束时，模型／工具总预算、传输重试、超时、取消仍待下步验证；业务语义仍未验收。

## 主循环第 3 步：预算、传输、超时与取消

新增测试均在 `tests/agent_loop/contract/`，仅验证本步执行边界，没有新增知识库、检索或 Q01～Q18 业务测试。

| 检查组 | 用例数 | 预期与实际 |
|---|---:|---|
| [预算与接纳](../tests/agent_loop/boundary/test_budgets.py) | 8 | 最后一轮合法终态可结束，需要工具则停止；模型／工具超限不追加总结；批量串行执行，重复、失败和错误参数均计数，输出工具不计数；全部通过 |
| [SDK 传输](../tests/agent_loop/boundary/test_transport.py) | 20 | 连接／读取超时及 429、500、502、503、504 最多重试一次；400、401、402、404、422、501 不重试；HTTP 上限不产生额外轮次／工具；资源关闭、不记录测试密钥或服务错误正文；全部通过 |
| [超时与取消](../tests/agent_loop/boundary/test_timeouts.py) | 10 | 单次模型超时取消等待，工具超时反馈模型；整轮时间包含初始快照和重试等待；在模型、工具、重试等待中超时或取消后无后续动作，保留已有证据；全部通过 |

实际结果：**38 passed in 3.13s**，见 [执行边界报告](../examples/agent_loop/reports/contract/agent-loop-execution-boundaries-results.xml)。前两步回归 **19 passed in 0.22s**，见 [回归报告](../examples/agent_loop/reports/contract/execution-boundaries-regression-results.xml)。冒烟回归 **5 passed，1 skipped in 0.90s**，见 [冒烟报告](../examples/integration/reports/smoke/execution-boundaries-smoke-results.xml)。跳过项为真实 API 冒烟，本步没有真实服务请求。

传输测试使用现有 OpenAI SDK 3.42.0、PydanticAI Provider 及生产 open_model 工厂；只把 HTTP 客户端传输替换为已锁定依赖 httpx2 的 MockTransport。测试使用伪密钥并继续封锁 socket／DNS，实际收到的本地请求数与应用计数一致，验证 SDK max_retries=0 未叠加隐式重试。该组保留 mode=real 是为了经过真实接入路径，不代表连通过 DeepSeek。其他用例使用 FunctionModel 受控响应。两者都不能计入真实模型决策成绩。

修正了两个原有边界问题：HTTP 额度耗尽后先阻止新逻辑轮次，避免虚增模型计数；批量工具先检查完整额度，避免只登记前几个请求却全部未执行。新 budgets 组件负责计数与接纳，执行钩子负责工具开始记录、异步超时及取消，PydanticAI 仍负责主循环。批次接纳后逐个计数，参数校验失败也不退还额度；取消时未启动的排队工具可有 requested 记录，但没有 started／result，不伪造其执行。

工具超时返回 TOOL_TIMEOUT，让模型选择下一步；不使用框架默认将超时算成参数修正的行为，也不自动重跑工具。整轮超时和用户取消不再发起模型总结，保留 observed_evidence；运行取消保存 user_cancelled 后继续向调用方传播取消，模型工厂资源释放。合法的模型 incomplete 结果仍按原结果保留，不被程序模板覆盖。

这些超时检查覆盖可协作取消的异步等待；当前工具只是内存中的小型资料读取。同步 CPU／阻塞 I/O 不能靠 asyncio 强行终止，后续 embedding 必须接入可终止的工作进程并另测。本步不包含完整 CLI 中断展示、操作系统信号专项或多轮历史生命周期。

```sh
python -m pytest tests/agent_loop/boundary/test_budgets.py tests/agent_loop/boundary/test_transport.py tests/agent_loop/boundary/test_timeouts.py -q --junitxml=examples/agent_loop/reports/contract/agent-loop-execution-boundaries-results.xml
python -m pytest tests/agent_loop/contract/test_normal_flow.py tests/agent_loop/contract/test_output_correction.py -q --junitxml=examples/agent_loop/reports/contract/execution-boundaries-regression-results.xml
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/execution-boundaries-smoke-results.xml
```

## 独立检索工具：BM25

本次按用户限定只开发并测试单工具，不接 Agent 主循环。实现默认目标 320／硬上限 480 tokens 的真实 BGE 分块、原文位置与指纹、jieba＋BM25Okapi、精确 ID 定位、过滤、固定排名分页、错误及证据记录。复用 F1，新增独立 F2 冲突原文；没有提前铺开完整业务矩阵。

新增 rank-bm25 0.2.2、jieba 0.42.1、tokenizers 0.22.1，实际间接依赖统一固定在 requirements.txt，pip check 通过。首次受限网络安装／下载失败，经授权后成功；测试阶段封锁网络。tokenizer revision 为 7999e1d3359715c523056ef9478215996d62a620，文件 SHA-256 及离线块再生成方式见 [预生成块说明](../data/prepared/README.md)。没有下载模型权重或调用模型 API。

| 层次 | 本次实际结果 | 代码与报告 |
|---|---|---|
| 冒烟 | 2 passed in 0.53s | [单工具启动／CLI](../tests/retrieval/smoke/test_search_smoke.py) · [报告](../examples/retrieval/reports/smoke/search-tool-results.xml) |
| 契约 | 38 passed in 6.34s | [工具参数与分页](../tests/retrieval/contract/test_search_tool.py)、[所需分块与版本](../tests/retrieval/contract/test_preparation.py) · [报告](../examples/retrieval/reports/contract/search-tool-results.xml) |
| 业务 | 7 passed in 1.64s | [检索效果](../tests/retrieval/business/test_search_effects.py) · [报告](../examples/retrieval/reports/business/search-tool-results.xml) |

47 项全部实际执行，无跳过。重新分块及资料替换相关测试使用本机已缓存的真实 tokenizer；若复现机器未显式下载，则这些项会明确跳过，不能将剩余通过数描述成全部通过。基础搜索与分页使用随仓库提供的块，无 tokenizer 文件也可离线执行。测试直接禁用 Agent.run／run_sync、模型网络请求和 socket／HTTP；没有执行原有 Agent 回归或联调测试。

契约检查覆盖无效参数不得启动检索、ID 去重／过滤、缺失部分 ID 的 partial、无候选与故障区分、原文与标题位置、词项匹配但分数非正的情况、稳定排序及分页、参数／快照变化拒绝旧游标、游标容量、正文限额不截半块、版本变化重建、覆盖完整性和真实 token 上限。分离标题与正文登记为多个真实 span，直接验证其可分别引用、不能拼成连续引文，没有调用 Agent。

业务预期为：支持条款进入默认前 5；无法消解的冲突保留双方；缺资料的指定查询返回空候选；明确 ID 返回对应来源；故障明确报错且不伪造证据；原文替换后检索新内容。实际过程全部保存：

| 用例 | 实际结果 | 材料 |
|---|---|---|
| 明确期限查询 | ok；返回 4 块，支持条款排名 3 | [输出](../examples/retrieval/outputs/normal/739ed1cdc4fb429087b13a6149e16d07/output.json) · [指标](../examples/retrieval/reports/normal/739ed1cdc4fb429087b13a6149e16d07/retrieval-evaluation.json) |
| 改写后的相似查询 | ok；返回 4 块，支持条款排名 3 | [输出](../examples/retrieval/outputs/paraphrase/48fa32f1c2c5427d8de3cea148f26bd6/output.json) · [指标](../examples/retrieval/reports/paraphrase/48fa32f1c2c5427d8de3cea148f26bd6/retrieval-evaluation.json) |
| 冲突双方召回 | ok；D01 的 30 天、D02 的 15 天均返回 | [输出](../examples/retrieval/outputs/conflicting_sources/89eb2183e5ad422db53f765c016f7f86/output.json) · [指标](../examples/retrieval/reports/conflicting_sources/89eb2183e5ad422db53f765c016f7f86/retrieval-evaluation.json) |
| 育儿假资料缺口 | empty；当前查询无词项匹配候选 | [输出](../examples/retrieval/outputs/out_of_corpus/8063cef779984265a898a47aab9d01d3/output.json) · [指标](../examples/retrieval/reports/out_of_corpus/8063cef779984265a898a47aab9d01d3/retrieval-evaluation.json) |
| 明确 D02 线索 | id_lookup；仅返回 D02 原文 | [输出](../examples/retrieval/outputs/explicit_document/e4d873e9f0b14fb6a1f1b5f4a69d28a3/output.json) · [指标](../examples/retrieval/reports/explicit_document/e4d873e9f0b14fb6a1f1b5f4a69d28a3/retrieval-evaluation.json) |
| 检索故障注入 | error／SEARCH_FAILED；证据数 0，不伪装 empty | [输出](../examples/retrieval/outputs/tool_failure/ef3f1f90946f42638fa96a75605c24cd/output.json) · [指标](../examples/retrieval/reports/tool_failure/ef3f1f90946f42638fa96a75605c24cd/retrieval-evaluation.json) |
| 原文 30 改 20 | 重准备后返回 20 天，未返回旧 30 天条款 | [输出](../examples/retrieval/outputs/policy_replacement/136e603a41384ad480edd8076438a085/output.json) · [指标](../examples/retrieval/reports/policy_replacement/136e603a41384ad480edd8076438a085/retrieval-evaluation.json) |

完整输入／输出／Trace 索引见 [单工具业务记录](../examples/retrieval/README.md)。记录明确 stage=standalone_search_tool、model_calls=0；没有最终 Agent 答案或模型行动，不能充当 Q01～Q18 的完整验收、真实 ReAct 路径或“三类 Agent 场景已覆盖”的证据。

**效果限制：** F1 两种问法的支持条款前 5 命中为 2/2，但首位命中为 0/2，均排在第 3 位；每次返回 4 块，标题和用途说明排在期限条款前。此处不把“找到支持资料”说成“排序已优化”。F2 本次冲突双方覆盖为 2/2，但资料仅两份，不能推广为复杂库的冲突召回保证。BM25 是词项检索，资料外问题如果与库中有公共词，仍可能返回无关候选；empty 仅表示本次查询无词项重合，不代表制度不存在。检索工具不判断适用范围或制度优先级。

当前 Markdown 分块支持 ATX 标题与围栏代码识别；没有完整 Markdown AST。索引标题上下文可截短并显式记录，原文与返回标题不截断。游标仅当前工具实例有效，容量有限；尚未做跨进程恢复（也不属于本项目恢复目标）。BM25 同步本地运行，未来 embedding worker 的终止与向量／混合分支仍需后续实现。

首次测试草稿因冒烟、契约文件同名而收集失败，重命名冒烟文件后正常执行；之后 47 项通过。主循环历史报告保持原样，本次修改了共享证据片段能力，但按用户范围没有用 Agent 做联调；后续接入时必须回归主循环。没有以当前单工具结果替代那一步。

```sh
python -m pytest tests/retrieval/smoke -q --junitxml=examples/retrieval/reports/smoke/search-tool-results.xml
python -m pytest tests/retrieval/contract -q --junitxml=examples/retrieval/reports/contract/search-tool-results.xml
python -m pytest tests/retrieval/business -q --junitxml=examples/retrieval/reports/business/search-tool-results.xml --examples-dir=examples
```

## 按模块与流程整理测试材料

按用户确认的结构，测试从顶层 smoke／contract／business 改为 retrieval、agent_loop、integration、e2e、support；模块内部按目的分类。原预算、传输与超时测试归 agent_loop/boundary，正常流程与输出校验归 contract。原 CLI＋占位工具冒烟归 integration/smoke，完整 e2e 尚未实现。

实际输入、输出与过程按 `examples/<范围>/{inputs,outputs,traces}/<case_id>/<run_id>/` 分开，报告归该范围 reports。Trace 对模块测试同样有效。11 组历史运行及历史报告共 115 个原始材料文件逐一校验 SHA-256，内容均未改变；不重写旧文件里的路径或运行环境。每组补充 artifacts.json 清单，记录分类后的路径和原始文件哈希。文档引用均已更新。

迁移前后测试发现均为 110 项，并逐项对比用例名称及参数化 ID，无漏项或新增业务场景。本次分别回归：

| 范围 | 实际结果 | 报告 |
|---|---|---|
| 独立检索 | 47 passed，8.05s | [检索整理回归](../examples/retrieval/reports/organization-results.xml) |
| 主循环受控测试 | 57 passed，3.10s | [主循环整理回归](../examples/agent_loop/reports/organization-results.xml) |
| 原 CLI 接入冒烟 | 5 passed、1 skipped，0.74s | [接入整理回归](../examples/integration/reports/smoke/organization-module-results.xml) |

共 109 passed、1 skipped。跳过真实 API 用例；没有真实模型请求，没有将新检索接入 Agent，也没有运行最终业务 e2e。主循环回归只验证目录和 fixture 调整后原有控制流仍正常。

为验证后续材料也按新结构生成，本次将 7 组检索业务和 1 组离线 CLI 运行通过 --examples-dir 导出到被忽略的 runtime/test-organization-export；核对 8 份清单的所有路径与哈希、inputs／outputs／traces 配对均通过。额外在临时目录检查重复导出不改变材料、不同内容拒绝覆盖；不把这些目录检查扩展成新的业务验收用例。本次保留上述自动化报告，历史实际材料继续供审阅，临时复测过程不重复提交。

复现（默认不导出临时材料；需要验证导出时对第一、第三条加 `--examples-dir=runtime/test-organization-export`）：

```sh
python -m pytest tests/retrieval -q --junitxml=examples/retrieval/reports/organization-results.xml
python -m pytest tests/agent_loop -q --junitxml=examples/agent_loop/reports/organization-results.xml
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/organization-module-results.xml
```

## 独立读取工具

按用户确认的范围，仅实现读取工具本身及单工具测试，不接 Agent 主循环。复用原文加载、RetrievalSnapshot、Section／Chunk ID、EvidenceStore、RunRecorder；没有另建一套正文、章节或证据身份。全文、章节、块读取分别返回实际原文范围；未知 ID、跨文档选择器、读取故障和超限分开报告。全文／章节超限不返回截断正文，只给每页最多 20 项定位；块读取不自动扩大到章节。

| 层次 | 实际结果 | 报告 |
|---|---|---|
| 冒烟 | 3 passed，0.02s | [读取冒烟](../examples/reading/reports/smoke/read-tool-results.xml) |
| 契约 | 23 passed，0.39s | [读取契约](../examples/reading/reports/contract/read-tool-results.xml) |
| 业务 | 7 passed，0.39s | [读取业务](../examples/reading/reports/business/read-tool-results.xml) |
| 边界 | 14 passed，1.06s | [读取边界](../examples/reading/reports/boundary/read-tool-results.xml) |
| 原检索回归 | 47 passed，8.06s | [搜索兼容回归](../examples/retrieval/reports/read-tool-compatibility-results.xml) |

读取共 47 项通过，无跳过；检索另 47 项通过。未运行 Agent 主循环或集成测试，未调用真实 API，没有新增依赖。读取基础测试只用提交的预生成块；超大章节、Unicode 原文和资料替换测试用已缓存的固定真实 tokenizer，复现机器未准备时会明确跳过，不得宣称全部通过。

实际输入、输出、Trace、证据和逐组指标在 [读取材料索引](../examples/reading/README.md)，通过 case_id／run_id 与 artifacts.json 关联。业务记录的结果为：

- 明确原文：全文分段拼接等于 Markdown 原文，保留国内差旅、行程结束和 30 天条件。
- 章节扩展：R1 的期限块不含第 9 条适用范围；按搜索结果的 section_id 读取后，取得“仅适用于国内差旅”的原文。同一 chunk_id 读取只返回原块及标题。
- 冲突来源：分别读取 D01 的 30 天与 D02 的 15 天，保留双方来源，不生成制度裁决。
- 缺失资料定位：D99 返回 NOT_FOUND 和具体目标，没有证据，不声称制度不存在。
- 工具故障：测试向 RetrievalSnapshot.get 注入一次 OSError；返回 READ_FAILED，实际尝试 1 次、证据 0，不自动重试或泄漏异常内容。
- 超限章节：340 字符预算下返回 CONTENT_TOO_LARGE 和 3 个块定位，随后按各 read_args 读取成功并取得范围条款；这些动作由测试发起。
- 资料替换：临时原文从 30 天改为 20 天；已打开快照保持原文，新装配重准备后读取 20 天，版本指纹改变；前后两次运行互相记录 run_id。

首次章节扩展测试从多个实际搜索候选中选取期限块，证明定位兼容，但不能证明首次整体观察缺少范围。为明确补读前提，随后收紧为 query=“草稿保存时间”、limit=1，实际唯一返回期限块；补读取得范围。针对变更用例复测 **1 passed，0.23s**，见 [收紧后的报告](../examples/reading/reports/business/section-expansion-refined-results.xml)。两次实际材料均保留并在索引中区分；不是失败后隐藏记录，也不是模型决定使用 limit=1。

边界测试另检查全文／章节恰好容纳与少 1 字符的区别、超过 20 项的定位完整性、选择器范围、块读取可恢复、跨工具／实例／快照游标拒绝、游标容量淘汰和重放、分离标题不得拼接引用、未反馈证据不得引用、无标题 ROOT 和 Unicode／CRLF。输入错误不访问来源，记录写入失败直接传播，不伪装成成功或 READ_FAILED。

**限制：** 所有运行 model_calls=0、delivered_to_model=false（引用校验单元测试仅在内存模拟投递标记）。不提供最终 Agent 答案，不计入真实 P2、冲突查证、工具恢复或六类题目验收。章节沿用现有 ATX Section 划分，没有新增章节树；同步内存工具未验证 Agent 异步超时。独立入口多次调用时 input/output 为最后一次，JSONL 保留全部过程；正式接入需将整轮材料写入职责交由运行器管理。

## 限制与下一阶段

- 独立检索阶段只验证单工具；目录整理时额外复跑原主循环与接入基线，仍未联通新检索。Q01～Q18 的完整 Agent 场景尚未验收，不报告 Agent 业务通过率。
- Agent 的 `smoke_fixture` 仍直接返回小型资料集；独立搜索已实现 BM25，尚未接入 Agent，不能把原冒烟描述为新检索联调。
- 独立搜索实现 BM25 搜索契约，独立读取已实现全文／章节／块及超限定位契约；两者尚未接入主循环，向量及混合搜索尚未实现。
- 真实接入已通过一次实际工具闭环；当前版本仍仅作为冒烟环境基线，完整接入契约待验证。
- 同批工具与终态、共享输出修正额度、模型／工具预算、错误参数计数、传输重试及异步超时／取消已受控验证；完整工具协议、CPU 工作进程及 CLI 中断展示仍待对应模块开发。
- 当前仅单题 CLI，没有历史、多轮问答或完整离线场景集合。
- 结构与精确引文校验通过不等于语义正确；当前 Mock 正常结果不计入真实决策路径数量。
