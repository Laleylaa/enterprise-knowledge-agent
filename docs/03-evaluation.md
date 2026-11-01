# 底座与端到端冒烟评估

记录日期：2026-11-01。当前维护接入底座、端到端冒烟及主循环三步契约，不代表 PRD 业务验收通过。

## 环境

macOS arm64；Python 3.11.15；PydanticAI 2.64.0；Pydantic 2.14.2；OpenAI SDK 3.42.0；pydantic-settings 2.16.2；pytest 9.2.0。完整版本统一保存在 `requirements.txt`。

安装时首次受网络沙箱限制失败；获得联网授权后安装成功。`pip check` 无依赖冲突，项目可编辑安装成功。

## 冒烟预期与实际结果

初始阶段命令（使用整理后的目录；当前范围调整后的结果见下文）：`python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/smoke-results.xml`。历史报告及运行材料已迁入 `examples/tests/smoke/`，原文件内容未改写。

实际：**5 passed，1 skipped**。机器记录：[smoke-results.xml](../examples/tests/smoke/reports/smoke-results.xml)。

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

- 离线运行：[输入](../examples/tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/input.json)、[工具结果](../examples/tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/tool-results.jsonl)、[实际模型适配层输入](../examples/tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/model-inputs.jsonl)、[Trace](../examples/tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/trace.jsonl)、[输出](../examples/tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/output.json)。
- 真实模式启动：[输入](../examples/tests/smoke/runs/real/b31b71e307f14fbe980e1843cb1f7712/input.json)、[Trace](../examples/tests/smoke/runs/real/b31b71e307f14fbe980e1843cb1f7712/trace.jsonl)、[输出](../examples/tests/smoke/runs/real/b31b71e307f14fbe980e1843cb1f7712/output.json)。缺少密钥，退出码 1，没有调用真实服务。这是配置中断记录，不是 DeepSeek 服务故障或模型决策证据。

每次实际模型／脚本响应保存在 Trace 的 model_response 事件；每次请求的公开消息、工具定义与指令保存在 model-inputs.jsonl。没有后续模型调用时不补造观察或决策。

## 真实模型冒烟补充记录

2026-11-01 用户在本机配置密钥后显式执行真实冒烟；没有修改业务代码或测试判据。

1. 首次在受限环境中运行，模型连接失败，有限重试后以 incomplete 结束：[失败测试报告](../examples/tests/smoke/reports/live-smoke-results.xml)、[实际 Trace](../examples/tests/smoke/runs/real/1f55c124a9804f9fb26850da0fd27fb4/trace.jsonl)。2 次请求尝试均为 ModelConnectionError，未取得模型响应；不归因为模型语义错误。
2. 获得联网授权后运行同一测试，**1 passed in 5.57s**：[测试报告](../examples/tests/smoke/reports/live-smoke-network-results.xml)、[实际输入](../examples/tests/smoke/runs/real/2f49173f9b8540b8af130a1e735b8430/input.json)、[Trace](../examples/tests/smoke/runs/real/2f49173f9b8540b8af130a1e735b8430/trace.jsonl)、[输出](../examples/tests/smoke/runs/real/2f49173f9b8540b8af130a1e735b8430/output.json)。

成功运行使用 deepseek-flash，整轮约 5.16 秒，4 次模型决策／HTTP 尝试、2 次业务工具调用。实际顺序为 search_knowledge → read_document → 首次结构化输出校验未通过 → 模型修正并结束。首个候选同时声明 resolved 和非空 gaps，被字段约束拒绝；模型收到反馈后，移除未被当前问题要求的延伸事项，最终回答“国内差旅报销须在行程结束后 30 天内提交”，引用 D01 对应原文，状态 resolved。AI 辅助核对本例最终条件、期限及引文与资料一致；尚不代表用户已完成人工验收。

两次运行分别记录为受限网络失败和联网成功，不隐藏首次失败，也不据单次成功宣称稳定性或完整契约通过。此前缺少密钥的记录继续保留为历史结果。

## 业务流程验证材料状态

`examples/traces/` 专门保存后续正常流、信息／资料不足、冲突、工具失败等业务流程的输入、实际输出和模型行动记录，按用例、变体、模式、运行 ID 分类。当前只有规范说明，业务验收尚未执行。

上述开发冒烟材料统一归 `examples/tests/smoke/`，只能证明当前检查范围内的程序链路；不能把缺少密钥或模型连接失败当作业务工具失败场景，也不能用已有文件组数代替至少三类业务场景与全部验收点的覆盖。后续本评估文档分别引用业务流程证据和开发测试报告。

目录整理后复跑默认冒烟，结果为 **5 passed，1 skipped**，见 [整理后报告](../examples/tests/smoke/reports/organization-smoke-results.xml)。另核对默认 CLI 试跑写入被忽略的 runtime/runs，文档链接均有效；没有为本次目录调整重新调用真实 API。迁移的 28 个历史证据文件逐个核对内容哈希一致。

## 历史测试范围调整

资料准备阶段曾提前生成全量用例规格、旧格式草稿及静态检查，后来又增加独立加载边界检查。这些与当前开发阶段不匹配，现按用户要求移除；Q01～Q18 的验收要求仍保留在 solution，随实际功能逐项实现。源数据契约继续使用 manifest＋独立 Markdown，F1 原文样例保留。

历史实际报告原样保留：[静态目录检查 3 passed](../examples/tests/smoke/reports/case-catalog-results.xml)、[当时回归 8 passed／1 skipped](../examples/tests/smoke/reports/data-baseline-smoke-results.xml)、[加载检查阶段 16 passed／1 skipped](../examples/tests/smoke/reports/document-source-smoke-results.xml)。这些报告反映当时的测试集合，不是当前测试清单，也不证明业务验收完成；其中已移除的测试不可再按旧命令复现。

## 当前冒烟范围

冒烟部分保留 tests/smoke/test_cli.py 与 test_live.py。新存储契约的最小检查已并入原有离线端到端：从 manifest 指向的 Markdown 读取原文，核对实际运行的资料快照、工具证据及引用一致。独立组件的完整契约与业务测试后续按功能进度补充。

本次实际结果：**5 passed，1 skipped in 0.85s**，见 [当前范围冒烟报告](../examples/tests/smoke/reports/scope-aligned-smoke-results.xml)。跳过项为需显式启用的真实 API 冒烟；本次没有真实 API 请求。

```sh
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/scope-aligned-smoke-results.xml
```

## 主循环第 1 步：正常继续与结束

PydanticAI 继续负责模型请求、工具分发与回到模型的循环；应用未另写固定步骤循环。run_turn 新增可选模型工厂注入点，默认仍使用原有真实／Mock 接入。契约测试仅替换模型响应，复用实际本地工具、证据登记、输出校验及记录路径；指令明确允许无需取证的直接澄清。

| 用例 | 预期 | 实际 |
|---|---|---|
| search_then_finish | 实际检索结果进入下次请求，终态使用返回的证据身份及原文；之后不再调用模型／工具 | 通过 |
| search_read_then_finish | 依据检索返回的文档 ID 继续读取，原文进入下次请求，再独立结束 | 通过 |
| clarification_can_finish_without_tools | 合法 needs_info 直接结束；一次模型响应、零工具、无虚构证据或工具记录 | 通过 |

代码：[test_normal_flow.py](../tests/contract/agent_loop/test_normal_flow.py)。使用显式命名的 FunctionModel 脚本，mode=mock，禁用真实请求和网络，不读取本地密钥。工具仍为 smoke_fixture，小型资料全集返回，不证明检索效果或模型语义能力。以上只验证正常控制流；未覆盖混合响应、错误修正、预算精确边界、重试、超时及取消。

实际契约结果 **3 passed in 0.47s**：[契约报告](../examples/tests/contract/reports/agent-loop-normal-results.xml)。原有冒烟回归 **5 passed，1 skipped in 0.86s**：[冒烟报告](../examples/tests/smoke/reports/agent-loop-normal-smoke-results.xml)。跳过真实 API 项，本步无真实模型调用、无业务验收 Trace。运行中输入／输出／工具记录保存在 pytest 临时目录，检查实际记录与模型请求的一致性；长期保留上述报告。

```sh
python -m pytest tests/contract/agent_loop/test_normal_flow.py -q --junitxml=examples/tests/contract/reports/agent-loop-normal-results.xml
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/agent-loop-normal-smoke-results.xml
```

## 主循环第 2 步：输出校验与修正

仅新增 [test_output_correction.py](../tests/contract/agent_loop/test_output_correction.py)，受控模型响应经过同一 PydanticAI 循环与本地工具。未新增知识资料、检索实现或业务验收用例。

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

输出修正契约 **16 passed in 0.37s**：[报告](../examples/tests/contract/reports/agent-loop-output-correction-results.xml)。第 1 步回归 **3 passed in 0.23s**：[正常路径报告](../examples/tests/contract/reports/agent-loop-normal-regression-results.xml)。冒烟回归 **5 passed，1 skipped in 0.84s**：[冒烟报告](../examples/tests/smoke/reports/output-correction-smoke-results.xml)。无真实 API 调用；测试中的模型修正是脚本行为，不证明真实模型会修正成功。

结构解析和反馈交给框架，应用钩子维护跨错误类型的输出修正额度。混合响应在交给框架执行前检查额度，避免 graceful 执行顺序让第三批工具先跑。额度耗尽以 output_retry_limit／incomplete 中断，已有原文仍由运行结果保留。测试核对实际下一次请求中的反馈、工具记录和终止次数，临时过程文件不作为业务验收 Trace。

```sh
python -m pytest tests/contract/agent_loop/test_output_correction.py -q --junitxml=examples/tests/contract/reports/agent-loop-output-correction-results.xml
python -m pytest tests/contract/agent_loop/test_normal_flow.py -q --junitxml=examples/tests/contract/reports/agent-loop-normal-regression-results.xml
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/output-correction-smoke-results.xml
```

第 2 步结束时，模型／工具总预算、传输重试、超时、取消仍待下步验证；业务语义仍未验收。

## 主循环第 3 步：预算、传输、超时与取消

新增测试均在 `tests/contract/agent_loop/`，仅验证本步执行边界，没有新增知识库、检索或 Q01～Q18 业务测试。

| 检查组 | 用例数 | 预期与实际 |
|---|---:|---|
| [预算与接纳](../tests/contract/agent_loop/test_budgets.py) | 8 | 最后一轮合法终态可结束，需要工具则停止；模型／工具超限不追加总结；批量串行执行，重复、失败和错误参数均计数，输出工具不计数；全部通过 |
| [SDK 传输](../tests/contract/agent_loop/test_transport.py) | 20 | 连接／读取超时及 429、500、502、503、504 最多重试一次；400、401、402、404、422、501 不重试；HTTP 上限不产生额外轮次／工具；资源关闭、不记录测试密钥或服务错误正文；全部通过 |
| [超时与取消](../tests/contract/agent_loop/test_timeouts.py) | 10 | 单次模型超时取消等待，工具超时反馈模型；整轮时间包含初始快照和重试等待；在模型、工具、重试等待中超时或取消后无后续动作，保留已有证据；全部通过 |

实际结果：**38 passed in 3.13s**，见 [执行边界报告](../examples/tests/contract/reports/agent-loop-execution-boundaries-results.xml)。前两步回归 **19 passed in 0.22s**，见 [回归报告](../examples/tests/contract/reports/execution-boundaries-regression-results.xml)。冒烟回归 **5 passed，1 skipped in 0.90s**，见 [冒烟报告](../examples/tests/smoke/reports/execution-boundaries-smoke-results.xml)。跳过项为真实 API 冒烟，本步没有真实服务请求。

传输测试使用现有 OpenAI SDK 3.42.0、PydanticAI Provider 及生产 open_model 工厂；只把 HTTP 客户端传输替换为已锁定依赖 httpx2 的 MockTransport。测试使用伪密钥并继续封锁 socket／DNS，实际收到的本地请求数与应用计数一致，验证 SDK max_retries=0 未叠加隐式重试。该组保留 mode=real 是为了经过真实接入路径，不代表连通过 DeepSeek。其他用例使用 FunctionModel 受控响应。两者都不能计入真实模型决策成绩。

修正了两个原有边界问题：HTTP 额度耗尽后先阻止新逻辑轮次，避免虚增模型计数；批量工具先检查完整额度，避免只登记前几个请求却全部未执行。新 budgets 组件负责计数与接纳，执行钩子负责工具开始记录、异步超时及取消，PydanticAI 仍负责主循环。批次接纳后逐个计数，参数校验失败也不退还额度；取消时未启动的排队工具可有 requested 记录，但没有 started／result，不伪造其执行。

工具超时返回 TOOL_TIMEOUT，让模型选择下一步；不使用框架默认将超时算成参数修正的行为，也不自动重跑工具。整轮超时和用户取消不再发起模型总结，保留 observed_evidence；运行取消保存 user_cancelled 后继续向调用方传播取消，模型工厂资源释放。合法的模型 incomplete 结果仍按原结果保留，不被程序模板覆盖。

这些超时检查覆盖可协作取消的异步等待；当前工具只是内存中的小型资料读取。同步 CPU／阻塞 I/O 不能靠 asyncio 强行终止，后续 embedding 必须接入可终止的工作进程并另测。本步不包含完整 CLI 中断展示、操作系统信号专项或多轮历史生命周期。

```sh
python -m pytest tests/contract/agent_loop/test_budgets.py tests/contract/agent_loop/test_transport.py tests/contract/agent_loop/test_timeouts.py -q --junitxml=examples/tests/contract/reports/agent-loop-execution-boundaries-results.xml
python -m pytest tests/contract/agent_loop/test_normal_flow.py tests/contract/agent_loop/test_output_correction.py -q --junitxml=examples/tests/contract/reports/execution-boundaries-regression-results.xml
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/execution-boundaries-smoke-results.xml
```

## 限制与下一阶段

- 当前验证主循环正常路径、输出修正及执行边界契约，不执行业务验收或检索效果评估。Q01～Q18 尚未验收，不报告业务通过率。
- `smoke_fixture` 直接返回小型资料集，不使用查询排名、不分块、不分页；输出显式标识，不冒充 BM25／vector／hybrid。
- 搜索和整篇读取工具仅实现最小参数子集，不宣称满足 solution 全部工具契约。
- 真实接入已通过一次实际工具闭环；当前版本仍仅作为冒烟环境基线，完整接入契约待验证。
- 同批工具与终态、共享输出修正额度、模型／工具预算、错误参数计数、传输重试及异步超时／取消已受控验证；完整工具协议、CPU 工作进程及 CLI 中断展示仍待对应模块开发。
- 当前仅单题 CLI，没有历史、多轮问答或完整离线场景集合。
- 结构与精确引文校验通过不等于语义正确；当前 Mock 正常结果不计入真实决策路径数量。
