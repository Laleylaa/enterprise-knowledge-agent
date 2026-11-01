# 测试范围与分类

当前维护启动、配置与端到端冒烟，以及主循环正常路径、输出修正、执行边界的契约测试，使用已确认的 Markdown 原文＋manifest 元数据清单。每实现一部分功能，再编写该部分测试；不提前生成全部业务用例或为尚未实现的接口固定测试格式。

| 当前文件 | 职责 |
|---|---|
| `smoke/test_cli.py` | 启动、配置优先级与脱敏、离线端到端、缺少密钥与非法配置的启动检查 |
| `smoke/test_live.py` | 显式启用的真实模型接入冒烟，默认跳过 |
| `contract/agent_loop/test_normal_flow.py` | 检索后结束、继续读取后结束、无工具直接澄清；仅验证框架控制流 |
| `contract/agent_loop/test_output_correction.py` | 结构／引用错误反馈、混合响应、共享输出修正额度；16 个参数化用例 |
| `contract/agent_loop/test_budgets.py` | 模型／工具上限、批量串行执行、参数错误与重复调用计数；8 项 |
| `contract/agent_loop/test_transport.py` | 真实 SDK＋本地 HTTP 模拟，验证错误分类、重试、HTTP 上限与资源关闭；20 项 |
| `contract/agent_loop/test_timeouts.py` | 模型／工具／整轮超时，模型／工具／重试等待时取消及材料保存；10 项 |
| `contract/agent_loop/conftest.py` | 只供主循环契约使用的本地配置与网络隔离 |
| `smoke/conftest.py` | 隔离本机配置，明确指定冒烟 manifest 与临时输出目录 |

离线端到端检查覆盖：读取 manifest 及 Markdown → 模型脚本选择工具 → 实际本地工具返回 → 结果与引用校验 → 保存输出及 Trace，并核对资料快照和引用来自原文。封锁网络、移除密钥，脚本结果不证明真实模型能力。

```sh
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/scope-aligned-smoke-results.xml
python -m pytest tests/contract/agent_loop/test_normal_flow.py -q --junitxml=examples/tests/contract/reports/agent-loop-normal-results.xml
python -m pytest tests/contract/agent_loop/test_output_correction.py -q --junitxml=examples/tests/contract/reports/agent-loop-output-correction-results.xml
python -m pytest tests/contract/agent_loop/test_budgets.py tests/contract/agent_loop/test_transport.py tests/contract/agent_loop/test_timeouts.py -q --junitxml=examples/tests/contract/reports/agent-loop-execution-boundaries-results.xml
# 仅在需要显式验证真实接入时运行
python -m pytest tests/smoke/test_live.py --run-live -q
```

当前契约测试在 `tests/contract/agent_loop/`，通过注入 PydanticAI FunctionModel 受控响应运行同一 runtime、实际工具及证据校验，不另写测试循环。传输测试改用实际 SDK 与 `httpx2.MockTransport`，仅允许本地模拟响应，socket／DNS 仍封锁；其他测试禁用真实模型请求。临时运行材料由 pytest 管理，交付测试报告在 examples/tests/contract/reports。脚本响应不证明真实模型决策效果。

第 2 步验证 ToolOutput 参数结构、引用和混合响应修正；第 3 步验证执行边界。批量请求超过剩余额度时整批拒绝且不计为接纳；额度充足时逐个计数，再串行执行，失败／参数错误／重复请求均占额度。工具超时返回错误交给模型，不自动重跑工具；整轮超时或取消停止后续调用并保存已有证据。异步超时测试不覆盖未来的 CPU embedding 工作进程。后续逐部分开发；多轮会话、业务验收及对应规格在实现时再创建测试，Q01～Q18 目前仍只在 solution 中规划。

## 材料保存

- 测试代码在 tests，实际测试报告在 `examples/tests/<类别>/reports/`；需要留存的调试记录在同类别 runs 下，普通中间文件使用临时目录。
- 正常流、异常流的业务实际输入、输出及过程保存在 `examples/traces/`，当前尚无业务验收记录。
- 日常试跑仍写入被 Git 忽略的 runtime；历史实际报告保留并注明对应阶段，不当作当前可复现的测试清单。
