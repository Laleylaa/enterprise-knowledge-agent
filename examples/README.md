# 验证材料分类

此目录按**验证用途**区分业务流程验证与开发测试，而非仅按真实／Mock 模式区分。

```text
examples/
  traces/                           # PRD 正常流、异常流的业务验证材料
    README.md                       # 当前仅说明规范，尚无业务验收记录
    <case_id>/<variant_id>/<mode>/<run_id>/       # 后续实际生成
  tests/
    smoke/
      reports/                      # 冒烟测试报告
      runs/<mode>/<run_id>/          # 冒烟输入、输出、资料及调试 Trace
    contract/reports/               # 主循环正常路径、输出修正与执行边界契约报告
    business/                       # 后续业务自动断言报告，尚未创建
```

`tests/`（仓库根目录）存放可执行代码；`examples/tests/` 存放实际执行材料。测试规格及预期由评估器读取，不能作为模型观察或伪装成实际输出。

## 当前材料索引

下表运行记录全部属于 `integration_smoke`，没有将冒烟记录改称完整业务验收。失败和成功材料均保留。

| 运行 | 用途／实际结果 | 输入、输出与过程 |
|---|---|---|
| `7882cbd51ad8437e9901d74fa081be6b` | 离线脚本冒烟成功；不证明真实决策 | [输入](tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/input.json) · [输出](tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/output.json) · [Trace](tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/trace.jsonl) |
| `b31b71e307f14fbe980e1843cb1f7712` | 缺少密钥，中断；没有真实请求 | [输入](tests/smoke/runs/real/b31b71e307f14fbe980e1843cb1f7712/input.json) · [输出](tests/smoke/runs/real/b31b71e307f14fbe980e1843cb1f7712/output.json) · [Trace](tests/smoke/runs/real/b31b71e307f14fbe980e1843cb1f7712/trace.jsonl) |
| `1f55c124a9804f9fb26850da0fd27fb4` | 受限环境连接失败；不是业务工具故障验收 | [输入](tests/smoke/runs/real/1f55c124a9804f9fb26850da0fd27fb4/input.json) · [输出](tests/smoke/runs/real/1f55c124a9804f9fb26850da0fd27fb4/output.json) · [Trace](tests/smoke/runs/real/1f55c124a9804f9fb26850da0fd27fb4/trace.jsonl) |
| `2f49173f9b8540b8af130a1e735b8430` | 真实模型冒烟成功；4 次决策、2 次工具 | [输入](tests/smoke/runs/real/2f49173f9b8540b8af130a1e735b8430/input.json) · [输出](tests/smoke/runs/real/2f49173f9b8540b8af130a1e735b8430/output.json) · [Trace](tests/smoke/runs/real/2f49173f9b8540b8af130a1e735b8430/trace.jsonl) |

测试报告：[默认冒烟](tests/smoke/reports/smoke-results.xml)、[受限连接失败](tests/smoke/reports/live-smoke-results.xml)、[联网真实冒烟通过](tests/smoke/reports/live-smoke-network-results.xml)。详细判定与限制见 [评估文档](../docs/03-evaluation.md)。

目录整理后的回归：[冒烟报告](tests/smoke/reports/organization-smoke-results.xml)，5 passed、1 skipped；未重新调用真实 API。

历史材料从旧目录迁移时只移动文件，逐个核验内容哈希一致；其中原始 input.json 的输出目录和 XML 的命令／源码上下文仍反映当时运行配置，不重写成新路径。

默认日常试跑输出到被 Git 忽略的 `runtime/runs/`。需要交付冒烟证据时使用 `--output-dir examples/tests/smoke/runs`；后续业务验证由对应入口显式指定 `examples/traces/<case_id>/`。不删除失败验收记录，也不将预期路径写成实际记录。

历史阶段报告：[静态规格检查](tests/smoke/reports/case-catalog-results.xml)、[当时回归](tests/smoke/reports/data-baseline-smoke-results.xml)、[加载检查阶段](tests/smoke/reports/document-source-smoke-results.xml)。对应的全量规格与独立检查已按开发范围清理，报告只保留历史事实，不作为当前测试覆盖或业务验收证据。

当前范围回归：[scope-aligned-smoke-results.xml](tests/smoke/reports/scope-aligned-smoke-results.xml)，5 passed、1 skipped；端到端读取 manifest＋Markdown，未调用真实 API。

主循环正常路径第 1 步：[契约报告](tests/contract/reports/agent-loop-normal-results.xml)（3 passed）、[冒烟回归](tests/smoke/reports/agent-loop-normal-smoke-results.xml)（5 passed、1 skipped）。受控模型＋实际本地工具，仅验证正常继续和结束，不计为真实业务决策证据。

主循环输出修正第 2 步：[输出修正契约报告](tests/contract/reports/agent-loop-output-correction-results.xml)（16 passed）、[正常路径回归](tests/contract/reports/agent-loop-normal-regression-results.xml)（3 passed）、[冒烟回归](tests/smoke/reports/output-correction-smoke-results.xml)（5 passed、1 skipped）。本地受控模型，仅验证程序协议和修正额度。

主循环执行边界第 3 步：[预算／传输／超时／取消报告](tests/contract/reports/agent-loop-execution-boundaries-results.xml)（38 passed）、[前两步回归](tests/contract/reports/execution-boundaries-regression-results.xml)（19 passed）、[冒烟回归](tests/smoke/reports/execution-boundaries-smoke-results.xml)（5 passed、1 skipped）。传输测试标记 mode=real 以运行真实 SDK，但 HTTP 由本地 MockTransport 替换，未连接服务；不作为真实 API 或业务决策证据。逐次输入输出在 pytest 临时目录验证，报告按契约／冒烟分类保存。
