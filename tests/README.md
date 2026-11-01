# 测试范围与分类

先按被测范围分目录：各模块、integration、e2e、support；模块和流程内部再按冒烟、契约、业务、边界分类。有实际用例才增加分类目录，不提前铺开全量业务测试。

```text
tests/
  retrieval/
    smoke/          # 独立工具启动与 CLI
    contract/       # 参数、返回、证据、分页、分块与版本协议
    business/       # 支持条款、改写、冲突召回、资料缺口及故障
  reading/
    smoke/          # 独立读取启动与 CLI
    contract/       # 选择器、来源／引用、搜索定位兼容与记录
    business/       # 全文、章节补读、冲突原文、资料缺失、故障及替换
    boundary/       # 超限定位、游标隔离／容量、预算边界与原文字符
  agent_loop/
    conftest.py     # 主循环局部 fixture，供契约与边界共享
    contract/       # 正常继续／结束、输出修正协议
    boundary/       # 预算、传输重试、超时与取消
  integration/
    smoke/          # 正式 CLI → 主循环 → 原占位工具的接入冒烟
    tool_calls/     # 模型 FC → 真实 BM25／读取 → 工具反馈，停在业务终态之前
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

## 当前读取工具

| 文件 | 范围 | 实际结果 |
|---|---|---|
| `reading/smoke/test_read_smoke.py` | 无 tokenizer／密钥／网络读取；CLI 成功与未知文档 | 3 passed |
| `reading/contract/test_read_tool.py` | 参数、全文／章节／块、跨文档定位、搜索 ID／证据兼容、精确引用和记录失败 | 23 passed |
| `reading/business/test_read_effects.py` | 明确原文、章节补读、冲突来源、缺失 ID、读取故障、超限局部读取及资料替换 | 7 passed |
| `reading/boundary/test_read_limits.py` | 多页定位不漏项、游标隔离／过期、字符预算边界、块预算防循环、Unicode／CRLF／ROOT | 14 passed |

```sh
python -m pytest tests/reading/smoke -q --junitxml=examples/reading/reports/smoke/current-results.xml
python -m pytest tests/reading/contract -q --junitxml=examples/reading/reports/contract/current-results.xml
python -m pytest tests/reading/business -q --junitxml=examples/reading/reports/business/current-results.xml --examples-dir=examples
python -m pytest tests/reading/boundary -q --junitxml=examples/reading/reports/boundary/current-results.xml
```

复用 retrieval_settings 封锁网络和 Agent；没有真实模型或主循环调用。R1 专项原文的预生成块支持离线章节补读；大型章节、无标题 Unicode 原文及资料替换测试使用本机固定 tokenizer 在临时目录正式准备，未安装 tokenizer 时相应项明确跳过。业务用例通过 archive_run 导出到 examples/reading；测试选择补读动作不等于模型自主决策。直接搜索与读取的兼容检查属于工具契约，不是 Agent 联调。

## 主循环与接入

主循环正常路径 3 项、输出修正 16 项；边界 38 项（预算 8、传输 20、超时与取消 10）。使用 FunctionModel 受控响应或实际 SDK＋本地 MockTransport，禁止真实网络。脚本行为只证明程序控制流与协议。

原接入冒烟为 5 个默认离线检查及 1 个需显式启用的真实 API 检查；覆盖配置、正式入口、manifest＋Markdown、原占位工具、引用校验与记录。正式工具的 FC 接入由下方独立测试范围验证，原冒烟不能当作题目的完整验收。

```sh
python -m pytest tests/agent_loop/contract -q --junitxml=examples/agent_loop/reports/contract/current-results.xml
python -m pytest tests/agent_loop/boundary -q --junitxml=examples/agent_loop/reports/boundary/current-results.xml
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/current-results.xml --examples-dir=examples
# 按范围和目的组合筛选
python -m pytest tests/retrieval -m smoke -q
# 仅在需要显式验证真实接入时运行，会使用 API 额度
python -m pytest tests/integration/smoke/test_live.py --run-live -q --examples-dir=examples
```

## 正式工具 FC 接入

`integration/tool_calls/test_function_binding.py` 有 12 项契约测试：搜索／ID 定位、三种读取范围、搜索后根据实际返回定位读取章节、搜索续页、超限定位到块读取、同批两个工具的 ID／顺序，以及三个无效参数反馈后成功修正的情况。使用 FunctionModel 提交 FC，实际执行正式工具，并在后续模型请求中核对完整返回、调用 ID、证据投递及每次请求的 schema；不直接从测试绕过框架调用工具。

`integration/tool_calls/test_provider_function_calls.py` 有 2 项协议测试：真实生产模型工厂、DeepSeek provider 和 SDK 经过本地 MockTransport，检查每次实际 HTTP 请求中的原生 tools[].function 定义、返回角色及 tool_call_id。HTTP 响应为测试注入，socket／DNS 禁止联网，mode=real 仅用于经过生产适配器，不是实际模型能力证据。

公共驱动在 `support/tool_calls.py`，使用实际 build_agent＋RecordedModel 和公开 Agent.iter，模型收到工具观察后即停止，未接受业务终态；输出仅汇总实际工具结果。调用开始只由执行钩子记录一次，工具不能覆盖运行器 input/output。新测试没有启动 CLI 会话或新增 E2E 业务验收。

```sh
python -m pytest tests/integration/tool_calls -q --junitxml=examples/integration/reports/tool_calls/current-results.xml --examples-dir=examples
```

本次 14 项通过；已有主循环、原冒烟、两个独立工具回归 156 passed／1 skipped，真实 API 默认跳过。固定预生成块足以执行全部新增接入测试，无 tokenizer 或模型权重依赖。输入、实际工具返回、模型请求和原生 HTTP 请求／响应见 [FC 材料索引](../examples/integration/tool-calls.md)。

## 材料保存

`tests/` 存代码；`examples/<模块或流程>/` 下分 inputs、outputs、traces、reports。所有范围都可以有 Trace。详情及历史实际运行索引见 [examples](../examples/README.md)。

默认运行仅使用 pytest 临时目录；加 `--examples-dir=examples` 后，已登记的检索业务运行与 CLI 冒烟运行在测试清理时导出，断言失败也保存已经产生的材料。不登记的小型参数断言只需测试报告。该参数不启用真实 API，真实调用仍必须加 `--run-live`。

公共导出器位于 `support/artifacts.py`：保留原始文件字节，用相同 case_id／run_id 分目录保存，并生成含路径及 SHA-256 的 artifacts.json。实际输入按运行留快照，不把后续修改的输入误配给旧结果；已有不同内容禁止覆盖。未来用例通过 archive_run fixture 登记，无须修改业务运行器。

JUnit 报告通过 `--junitxml` 单独指定。示例中的 current-results.xml 是最新结果；需要保留多次结果时使用不同文件名。原历史报告原样保留，内部旧源码路径反映当时阶段，不宣称为当前测试清单。support 是辅助代码，不在 examples 下建立镜像目录。
