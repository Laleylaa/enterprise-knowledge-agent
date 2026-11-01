# 验证材料分类

按被测范围与 tests 对应组织，再在各范围下分开保存输入、实际输出、中间过程及测试报告。Trace 可以来自模块、集成或完整端到端测试，不代表其本身就是最终业务验收。

```text
examples/
  retrieval/                   # 独立检索组件
    inputs/<case_id>/<run_id>/
    outputs/<case_id>/<run_id>/
    traces/<case_id>/<run_id>/
    reports/<category>/        # JUnit 汇总报告
    reports/<case_id>/<run_id>/ # 每次执行的效果核对
  agent_loop/
    reports/                   # 当前只选留报告；单次运行在 pytest 临时目录
  reading/                     # 独立读取工具，含直接搜索定位到读取的契约记录
    inputs/, outputs/, traces/, reports/
  integration/                 # 当前 CLI 与占位工具接入冒烟
    inputs/, outputs/, traces/, reports/
  e2e/                         # 最终题目验收，当前只有说明
```

同一次运行通过 case_id／run_id 关联三个目录。每次保留实际输入快照，包含资料／索引配置；traces 中的 artifacts.json 列出当次文件路径与 SHA-256。工具参数、工具返回和证据属于执行中间过程；最终结果与运行摘要放 outputs；评估侧指标放 reports，不作为模型输入。

可执行代码在仓库根目录 tests。support 是辅助代码，无需材料镜像。未产生材料的分类不建空目录。e2e 的范围和真实／Mock 边界见 [完整验收说明](e2e/README.md)。

最新独立读取材料见 [reading/README.md](reading/README.md)：47 项测试通过，业务记录包括正常、章节补读、冲突双方原文、缺失 ID、注入读取故障、超限局部读取和资料替换。均为工具直接调用，不接 Agent，不作为真实决策或完整 Q01～Q18 验收成绩。

## 当前材料索引

下表运行记录全部属于 `integration_smoke`，没有将冒烟记录改称完整业务验收。失败和成功材料均保留。

| 运行 | 用途／实际结果 | 输入、输出与过程 |
|---|---|---|
| `7882cbd51ad8437e9901d74fa081be6b` | 离线脚本冒烟成功；不证明真实决策 | [输入](integration/inputs/cli_mock/7882cbd51ad8437e9901d74fa081be6b/input.json) · [输出](integration/outputs/cli_mock/7882cbd51ad8437e9901d74fa081be6b/output.json) · [Trace](integration/traces/cli_mock/7882cbd51ad8437e9901d74fa081be6b/trace.jsonl) |
| `b31b71e307f14fbe980e1843cb1f7712` | 缺少密钥，中断；没有真实请求 | [输入](integration/inputs/cli_real/b31b71e307f14fbe980e1843cb1f7712/input.json) · [输出](integration/outputs/cli_real/b31b71e307f14fbe980e1843cb1f7712/output.json) · [Trace](integration/traces/cli_real/b31b71e307f14fbe980e1843cb1f7712/trace.jsonl) |
| `1f55c124a9804f9fb26850da0fd27fb4` | 受限环境连接失败；不是业务工具故障验收 | [输入](integration/inputs/cli_real/1f55c124a9804f9fb26850da0fd27fb4/input.json) · [输出](integration/outputs/cli_real/1f55c124a9804f9fb26850da0fd27fb4/output.json) · [Trace](integration/traces/cli_real/1f55c124a9804f9fb26850da0fd27fb4/trace.jsonl) |
| `2f49173f9b8540b8af130a1e735b8430` | 真实模型冒烟成功；4 次决策、2 次工具 | [输入](integration/inputs/cli_real/2f49173f9b8540b8af130a1e735b8430/input.json) · [输出](integration/outputs/cli_real/2f49173f9b8540b8af130a1e735b8430/output.json) · [Trace](integration/traces/cli_real/2f49173f9b8540b8af130a1e735b8430/trace.jsonl) |

测试报告：[默认冒烟](integration/reports/smoke/smoke-results.xml)、[受限连接失败](integration/reports/smoke/live-smoke-results.xml)、[联网真实冒烟通过](integration/reports/smoke/live-smoke-network-results.xml)。详细判定与限制见 [评估文档](../docs/03-evaluation.md)。

目录整理后的回归：[冒烟报告](integration/reports/smoke/organization-smoke-results.xml)，5 passed、1 skipped；未重新调用真实 API。

历史材料从旧目录迁移时只移动文件，逐个核验内容哈希一致；其中原始 input.json 的输出目录和 XML 的命令／源码上下文仍反映当时运行配置，不重写成新路径。

默认日常试跑输出到被 Git 忽略的 `runtime/runs/`；自动测试默认使用临时目录。需要归档已登记的检索业务或 CLI 冒烟运行时加 `--examples-dir=examples`，由 tests/support/artifacts.py 按统一格式导出；JUnit 由 --junitxml 单独指定。命令见 [测试说明](../tests/README.md)。不删除失败记录，也不将预期路径写成实际记录。

历史阶段报告：[静态规格检查](integration/reports/smoke/case-catalog-results.xml)、[当时回归](integration/reports/smoke/data-baseline-smoke-results.xml)、[加载检查阶段](integration/reports/smoke/document-source-smoke-results.xml)。对应的全量规格与独立检查已按开发范围清理，报告只保留历史事实，不作为当前测试覆盖或业务验收证据。

当前范围回归：[scope-aligned-smoke-results.xml](integration/reports/smoke/scope-aligned-smoke-results.xml)，5 passed、1 skipped；端到端读取 manifest＋Markdown，未调用真实 API。

主循环正常路径第 1 步：[契约报告](agent_loop/reports/contract/agent-loop-normal-results.xml)（3 passed）、[冒烟回归](integration/reports/smoke/agent-loop-normal-smoke-results.xml)（5 passed、1 skipped）。受控模型＋实际本地工具，仅验证正常继续和结束，不计为真实业务决策证据。

主循环输出修正第 2 步：[输出修正契约报告](agent_loop/reports/contract/agent-loop-output-correction-results.xml)（16 passed）、[正常路径回归](agent_loop/reports/contract/agent-loop-normal-regression-results.xml)（3 passed）、[冒烟回归](integration/reports/smoke/output-correction-smoke-results.xml)（5 passed、1 skipped）。本地受控模型，仅验证程序协议和修正额度。

主循环执行边界第 3 步：[预算／传输／超时／取消报告](agent_loop/reports/contract/agent-loop-execution-boundaries-results.xml)（38 passed）、[前两步回归](agent_loop/reports/contract/execution-boundaries-regression-results.xml)（19 passed）、[冒烟回归](integration/reports/smoke/execution-boundaries-smoke-results.xml)（5 passed、1 skipped）。传输测试标记 mode=real 以运行真实 SDK，但 HTTP 由本地 MockTransport 替换，未连接服务；不作为真实 API 或业务决策证据。逐次输入输出在 pytest 临时目录验证，报告归对应模块或 integration，内部再按类别保存。

独立 BM25 检索工具：[冒烟 2 passed](retrieval/reports/smoke/search-tool-results.xml)、[契约 38 passed](retrieval/reports/contract/search-tool-results.xml)、[业务 7 passed](retrieval/reports/business/search-tool-results.xml)。实际输入、输出、Trace 和效果指标见 [单工具记录索引](retrieval/README.md)。只执行工具，不调用模型，不作为完整 Agent 验收。F1 两种问法均取得支持条款，但其排名均为第 3 位；该限制在评估中保留。

## 当前目录整理回归

[检索 47 passed](retrieval/reports/organization-results.xml)、[主循环 57 passed](agent_loop/reports/organization-results.xml)、[接入冒烟 5 passed／1 skipped](integration/reports/smoke/organization-module-results.xml)。110 项原有用例逐项保留，历史运行及报告共 115 个原始文件哈希一致；11 组运行补充关联清单。完整 e2e 未执行，未调用真实 API，未接入新检索。新导出验证的 8 组临时运行留在被忽略的 runtime，细节见 [评估文档](../docs/03-evaluation.md)。
