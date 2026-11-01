# 测试范围与分类

先按被测范围分目录：各模块、integration、e2e、support；模块和流程内部再按冒烟、契约、业务、边界分类。有实际用例才增加分类目录，不提前铺开全量业务测试。

```text
tests/
  retrieval/
    smoke/          # 独立工具启动与 CLI
    contract/       # 参数、返回、证据、分页、分块与版本协议
    business/       # 支持条款、改写、冲突召回、资料缺口及故障
  agent_loop/
    conftest.py     # 主循环局部 fixture，供契约与边界共享
    contract/       # 正常继续／结束、输出修正协议
    boundary/       # 预算、传输重试、超时与取消
  integration/
    smoke/          # 正式 CLI → 主循环 → 原占位工具的接入冒烟
  e2e/              # 最终完整业务验收；当前仅有范围说明
  support/          # 可复用 fixture、隔离与材料导出
```

目录表示主要验证目的；例如分页极值同时属于接口契约，不为满足分类数量重复编写用例。pytest 的 smoke、contract、business、boundary 标记与分类对应，可用 `-m` 筛选。检索业务测试只检查工具业务行为，不等于完整 Agent 业务验收。

## 当前检索工具

| 文件 | 范围 | 已有实际结果 |
|---|---|---|
| `retrieval/smoke/test_search_smoke.py` | 无 tokenizer／密钥／网络的工具启动与 CLI | 2 passed |
| `retrieval/contract/test_search_tool.py` | 参数、原文证据、ID 过滤、部分错误、排序、分页、预算和故障 | 25 passed |
| `retrieval/contract/test_preparation.py` | 章节／块、真实 tokenizer 预算、快照／索引失效、原文覆盖 | 13 passed |
| `retrieval/business/test_search_effects.py` | 明确条款、改写、冲突双方、资料外查询、线索、故障及替换 | 7 passed |

```sh
python -m pytest tests/retrieval/smoke -q --junitxml=examples/retrieval/reports/smoke/current-results.xml
python -m pytest tests/retrieval/contract -q --junitxml=examples/retrieval/reports/contract/current-results.xml
python -m pytest tests/retrieval/business -q --junitxml=examples/retrieval/reports/business/current-results.xml --examples-dir=examples
```

测试直接执行 SearchTool，封锁 Agent.run／run_sync、真实模型请求与网络，未接入 Agent 主循环。基础检索使用已提交的预生成块；真实重分块测试需要显式下载固定 tokenizer，缺失时明确跳过，不用字符计数 Mock 替代。临时压力文本与资料替换只写临时目录。

## 主循环与接入

主循环正常路径 3 项、输出修正 16 项；边界 38 项（预算 8、传输 20、超时与取消 10）。使用 FunctionModel 受控响应或实际 SDK＋本地 MockTransport，禁止真实网络。脚本行为只证明程序控制流与协议。

接入冒烟为 5 个默认离线检查及 1 个需显式启用的真实 API 检查；覆盖配置、正式入口、manifest＋Markdown、原占位工具、引用校验与记录。当前真实检索尚未接入，不能当作题目的完整验收。

```sh
python -m pytest tests/agent_loop/contract -q --junitxml=examples/agent_loop/reports/contract/current-results.xml
python -m pytest tests/agent_loop/boundary -q --junitxml=examples/agent_loop/reports/boundary/current-results.xml
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/current-results.xml --examples-dir=examples
# 按范围和目的组合筛选
python -m pytest tests/retrieval -m smoke -q
# 仅在需要显式验证真实接入时运行，会使用 API 额度
python -m pytest tests/integration/smoke/test_live.py --run-live -q --examples-dir=examples
```

## 材料保存

`tests/` 存代码；`examples/<模块或流程>/` 下分 inputs、outputs、traces、reports。所有范围都可以有 Trace。详情及历史实际运行索引见 [examples](../examples/README.md)。

默认运行仅使用 pytest 临时目录；加 `--examples-dir=examples` 后，已登记的检索业务运行与 CLI 冒烟运行在测试清理时导出，断言失败也保存已经产生的材料。不登记的小型参数断言只需测试报告。该参数不启用真实 API，真实调用仍必须加 `--run-live`。

公共导出器位于 `support/artifacts.py`：保留原始文件字节，用相同 case_id／run_id 分目录保存，并生成含路径及 SHA-256 的 artifacts.json。实际输入按运行留快照，不把后续修改的输入误配给旧结果；已有不同内容禁止覆盖。未来用例通过 archive_run fixture 登记，无须修改业务运行器。

JUnit 报告通过 `--junitxml` 单独指定。示例中的 current-results.xml 是最新结果；需要保留多次结果时使用不同文件名。原历史报告原样保留，内部旧源码路径反映当时阶段，不宣称为当前测试清单。support 是辅助代码，不在 examples 下建立镜像目录。
