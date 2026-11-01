# 底座与端到端冒烟评估

记录日期：2026-11-01。当前仅维护接入底座与端到端冒烟，不代表 PRD 业务验收通过。

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

当前仅保留 tests/smoke/test_cli.py 与 test_live.py。新存储契约的最小检查已并入原有离线端到端：从 manifest 指向的 Markdown 读取原文，核对实际运行的资料快照、工具证据及引用一致。独立组件的完整契约与业务测试后续按功能进度补充。

本次实际结果：**5 passed，1 skipped in 0.85s**，见 [当前范围冒烟报告](../examples/tests/smoke/reports/scope-aligned-smoke-results.xml)。跳过项为需显式启用的真实 API 冒烟；本次没有真实 API 请求。

```sh
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/scope-aligned-smoke-results.xml
```

## 限制与下一阶段

- 此阶段不执行契约测试、业务验收或检索效果评估。Q01～Q18 尚未验收，不报告业务通过率。
- `smoke_fixture` 直接返回小型资料集，不使用查询排名、不分块、不分页；输出显式标识，不冒充 BM25／vector／hybrid。
- 搜索和整篇读取工具仅实现最小参数子集，不宣称满足 solution 全部工具契约。
- 真实接入已通过一次实际工具闭环；当前版本仍仅作为冒烟环境基线，完整接入契约待验证。
- 同批工具与终态、修正预算、错误参数计数、传输重试与取消等边界尚未进行契约验证；现有基础守卫不替代这些检查。
- 当前仅单题 CLI，没有历史、多轮问答或完整离线场景集合。
- 结构与精确引文校验通过不等于语义正确；当前 Mock 正常结果不计入真实决策路径数量。
