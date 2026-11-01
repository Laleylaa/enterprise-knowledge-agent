# 测试范围与分类

当前只维护启动、配置与端到端冒烟，使用已确认的 Markdown 原文＋manifest 元数据清单。每实现一部分功能，再编写该部分测试；不提前生成全部业务用例或为尚未实现的接口固定测试格式。

| 当前文件 | 职责 |
|---|---|
| `smoke/test_cli.py` | 启动、配置优先级与脱敏、离线端到端、缺少密钥与非法配置的启动检查 |
| `smoke/test_live.py` | 显式启用的真实模型接入冒烟，默认跳过 |
| `smoke/conftest.py` | 隔离本机配置，明确指定冒烟 manifest 与临时输出目录 |

离线端到端检查覆盖：读取 manifest 及 Markdown → 模型脚本选择工具 → 实际本地工具返回 → 结果与引用校验 → 保存输出及 Trace，并核对资料快照和引用来自原文。封锁网络、移除密钥，脚本结果不证明真实模型能力。

```sh
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/scope-aligned-smoke-results.xml
# 仅在需要显式验证真实接入时运行
python -m pytest tests/smoke/test_live.py --run-live -q
```

后续工具／组件契约测试放 `tests/contract/`，业务验收放 `tests/business/`，对应场景输入与预期按需放 `tests/cases/`。这些目录和测试等到对应功能开发时再创建；Q01～Q18 当前仅为 solution 中的验收计划。

## 材料保存

- 测试代码在 tests，实际测试报告在 `examples/tests/<类别>/reports/`；需要留存的调试记录在同类别 runs 下，普通中间文件使用临时目录。
- 正常流、异常流的业务实际输入、输出及过程保存在 `examples/traces/`，当前尚无业务验收记录。
- 日常试跑仍写入被 Git 忽略的 runtime；历史实际报告保留并注明对应阶段，不当作当前可复现的测试清单。
