# 企业知识问答 Agent

当前阶段：**主循环基线、独立 BM25 检索及独立原文读取工具已建立**。两个正式工具均尚未接入 Agent。

现有 Agent 的 `smoke` 入口仍使用 `data/smoke/manifest.json`，其占位搜索返回资料全集并标记 `smoke_fixture`。新检索通过下方独立入口执行真实 BM25，支持过滤、精确 ID 定位和分页；向量、混合检索仍未实现。

知识库统一采用 [Markdown 原文＋元数据清单](data/README.md)，目前有最小冒烟资料、F1 单规则、F2 冲突和 R1 章节补读资料，以及正式生成的离线原文块。Q01～Q18 的 Agent 验收仍未执行，不将单工具效果计为 Agent 验收成绩。

## 环境与安装

已在 macOS arm64、Python **3.11.15** 验证离线冒烟。系统默认 Python 可能是 3.9，请使用 Python 3.11。

从仓库根目录执行：

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` 是唯一依赖清单，包含运行、冒烟测试及已固定版本的间接依赖，用于复现本阶段环境。依赖已通过安装、依赖一致性、离线及真实 API 冒烟检查，完整契约验证尚未完成。`pyproject.toml` 读取同一清单，用于项目打包、命令入口和测试配置，不另维护一套依赖。

可直接使用下方 `PYTHONPATH=src` 命令，无须安装项目本身。可选执行 `python -m pip install -e .` 后使用 `knowledge-agent` 命令。

## 运行

### 独立检索工具

依赖安装后，使用仓库内预生成块即可离线搜索，无须密钥或 tokenizer 文件：

```sh
PYTHONPATH=src python -m knowledge_agent.retrieval search \
  --corpus data/fixtures/F1_single_rule/manifest.json \
  --prepared data/prepared/F1_single_rule.json \
  --query "国内差旅报销期限多久？" --output-dir runtime/search-tool
```

返回原文块、出处、证据 ID、工具执行状态和分页信息，不生成最终业务答案。运行目录记录 `stage=standalone_search_tool`、`model_calls=0`。一次 CLI 运行返回一页；连续翻页使用同一 `SearchTool` 实例的 Python 接口，见 [单工具说明](src/knowledge_agent/retrieval/README.md)。

首次准备或修改资料后重分块，需要显式下载固定版本的 BGE tokenizer（约 439 KB，无模型权重），之后可离线 prepare：

```sh
PYTHONPATH=src python -m knowledge_agent.retrieval download-tokenizer
PYTHONPATH=src python -m knowledge_agent.retrieval prepare \
  --corpus data/fixtures/F1_single_rule/manifest.json \
  --prepared data/prepared/F1_single_rule.json
```

搜索启动时校验原文、配置和派生块指纹；过期且本地 tokenizer 齐备时重建，否则明确要求 prepare，不使用过期块或自动联网。下载文件和 jieba 缓存留在被忽略的 `runtime/`。检索／分块参数统一由 Settings 和 `.env.example` 管理。

只运行本次单工具测试：

```sh
python -m pytest tests/retrieval/smoke -q
python -m pytest tests/retrieval/contract -q
python -m pytest tests/retrieval/business -q
```

实际结果为 **2／38／7 项通过**。搜索及分页测试直接使用离线块；重新分块、资料替换等测试使用真实本地 tokenizer，未下载时会明确跳过相应项。三类测试均封锁网络和 Agent 调用；本次未运行 Agent 联调测试。

当前两种报销问法均在前 5 个候选中取得支持条款，但支持条款都位于第 3 位；冲突双方均取得。小型资料集上的结果不代表复杂知识库效果，详情及实际记录见 [评估](docs/03-evaluation.md#独立检索工具bm25)。

### 独立读取工具（本次开发入口）

```sh
PYTHONPATH=src python -m knowledge_agent.reading \
  --corpus data/fixtures/F1_single_rule/manifest.json \
  --prepared data/prepared/F1_single_rule.json \
  --doc-id D01 --output-dir runtime/read-tool
```

可选 `--section-id` 或 `--chunk-id`，分别读取章节或块；不传则读取全文。定位来自同一资料快照的搜索结果。全文／章节超过预算时返回 `CONTENT_TOO_LARGE` 和局部读取定位，不截断正文。游标续页使用同一工具实例，详见 [读取工具说明](src/knowledge_agent/reading/README.md)。该入口不调用 Agent 或模型。

```sh
python -m pytest tests/reading/smoke -q
python -m pytest tests/reading/contract -q
python -m pytest tests/reading/business -q --examples-dir=examples
python -m pytest tests/reading/boundary -q
```

读取测试共 47 项：冒烟 3、契约 23、业务 7、边界 14。测试封锁网络和 Agent；部分重准备／压力用例需要本地固定 tokenizer，缺失时明确跳过。实际材料与报告见 [读取工具记录](examples/reading/README.md)。章节扩展由测试直接调用验证，不作为模型自主补读或 P2 真实路径证据。

### 离线冒烟

```sh
PYTHONPATH=src python -m knowledge_agent smoke --mode mock
```

不需要密钥、模型权重或运行时网络；首次安装依赖仍需网络或本地安装包。Mock 仅支持固定问题“国内差旅报销期限多久？”和当前冒烟资料。它使用预设模型脚本调用真实本地工具，不证明真实模型决策效果，也不是 solution 中的完整 Mock 场景集合。

标准输出为 JSON，包含回答、引用、缺口、状态、真实／Mock 模式、来源标记、计数及已取得原文；材料目录写到标准错误。正常离线运行应有两次脚本决策、一次业务工具调用、零次 HTTP 尝试。

日常试跑默认保存到被 Git 忽略的 `runtime/runs/`。需要留作开发测试证据时，通过接入冒烟测试导出分类材料：

```sh
python -m pytest tests/integration/smoke/test_cli.py -q --examples-dir=examples
```

### 真实模型冒烟

首次配置可复制 `.env.example` 为本地 `.env`，只在本机填写 `DEEPSEEK_API_KEY`，也可直接设置系统环境变量。`.env` 已被 Git 忽略。

```sh
PYTHONPATH=src python -m knowledge_agent smoke --mode real
```

使用 DeepSeek `deepseek-flash`，非流式、thinking 关闭。真实调用会使用 API 额度。没有密钥时返回 `incomplete / missing_api_key`，保存明确的中断记录，退出码为 1；不自动改用 Mock。

### 配置与帮助

```sh
PYTHONPATH=src python -m knowledge_agent config
PYTHONPATH=src python -m knowledge_agent --help
```

配置全部集中在 `src/knowledge_agent/config.py`，每次启动加载一次并显式传给各组件。优先级：**CLI 参数 > 系统环境变量 > 当前工作目录的 `.env` > 默认值**。路径相对于启动目录；建议始终在仓库根目录运行。配置导出只显示密钥是否存在，不输出密钥值。

主要配置见 `.env.example`：模型、资料及输出路径、模型轮次、HTTP 尝试、工具次数、输出修正、单次及整轮超时。上述边界已有本地受控验证；模型传输最多重试一次，超限返回 incomplete，取消时尽力保存已有证据。工具超时目前覆盖可取消的异步调用；后续本地 embedding 仍需可终止的工作进程。Agent 入口仍只有 `smoke` 与 `config`；工具的独立准备、搜索和读取入口不等于 solution 规划的统一 `chat / prepare / evaluate`。

退出码：0 表示本轮正常交付（包括正常的未解决／待补充）；1 表示未完成；2 表示配置、输入或材料读写失败；130 表示用户中断。

## 测试与评审入口

```sh
# CLI 接入冒烟；真实 API 用例默认跳过
python -m pytest tests/integration/smoke -q --junitxml=examples/integration/reports/smoke/current-results.xml

# 配好本机密钥后，显式执行真实模型冒烟
python -m pytest tests/integration/smoke/test_live.py --run-live -q --examples-dir=examples
```

测试先按模块、integration、e2e 分范围，再在内部按冒烟、契约、业务、边界分类，详见 [tests/README.md](tests/README.md)。正常路径 3 项，输出修正 16 项，执行边界 38 项（预算 8、传输 20、超时与取消 10）。后者使用受控模型及 SDK 本地 HTTP 模拟，封锁网络，不调用真实 API；不证明业务语义或真实服务稳定性。

```sh
python -m pytest tests/agent_loop/contract/test_normal_flow.py -q --junitxml=examples/agent_loop/reports/contract/agent-loop-normal-results.xml
python -m pytest tests/agent_loop/contract/test_output_correction.py -q --junitxml=examples/agent_loop/reports/contract/agent-loop-output-correction-results.xml
python -m pytest tests/agent_loop/boundary -q --junitxml=examples/agent_loop/reports/boundary/current-results.xml
```

材料按同一范围存入 `examples/<模块或流程>/`，下分 `inputs/`、`outputs/`、`traces/`、`reports/`；用例 ID 与运行 ID 关联同次执行。Trace 同样适用于模块测试。`examples/e2e/` 留给最终完整业务验收，目前未执行。完整索引见 [examples/README.md](examples/README.md)。

- 当前目录整理回归：检索 47、主循环 57、接入冒烟 5 项通过，真实 API 1 项跳过；[评估与报告](docs/03-evaluation.md)。
- [执行边界：38 passed](examples/agent_loop/reports/contract/agent-loop-execution-boundaries-results.xml)；[前两步回归：19 passed](examples/agent_loop/reports/contract/execution-boundaries-regression-results.xml)；[冒烟回归：5 passed，1 skipped](examples/integration/reports/smoke/execution-boundaries-smoke-results.xml)
- [输出修正契约：16 passed](examples/agent_loop/reports/contract/agent-loop-output-correction-results.xml)；[冒烟回归：5 passed，1 skipped](examples/integration/reports/smoke/output-correction-smoke-results.xml)
- [主循环正常路径契约：3 passed](examples/agent_loop/reports/contract/agent-loop-normal-results.xml)；[对应冒烟回归：5 passed，1 skipped](examples/integration/reports/smoke/agent-loop-normal-smoke-results.xml)
- [当前冒烟：5 passed，1 skipped](examples/integration/reports/smoke/scope-aligned-smoke-results.xml)
- [初始冒烟：5 passed，1 skipped](examples/integration/reports/smoke/smoke-results.xml)
- [显式真实模型冒烟：1 passed](examples/integration/reports/smoke/live-smoke-network-results.xml)；[实际输出](examples/integration/outputs/cli_real/2f49173f9b8540b8af130a1e735b8430/output.json)。首次受限环境连接失败的记录另见评估文档。
- [离线冒烟实际输出](examples/integration/outputs/cli_mock/7882cbd51ad8437e9901d74fa081be6b/output.json)
- [离线冒烟 Trace](examples/integration/traces/cli_mock/7882cbd51ad8437e9901d74fa081be6b/trace.jsonl)
- [真实模式缺少密钥的中断记录](examples/integration/outputs/cli_real/b31b71e307f14fbe980e1843cb1f7712/output.json)：没有发送真实 API 请求，不能作为真实模型效果证据。

## 组件职责

```text
src/knowledge_agent/
  __main__.py, cli.py       # 入口、参数与组件装配
  config.py                # 统一配置及脱敏导出
  schemas.py, errors.py     # 独立数据结构及错误
  context.py               # 每轮依赖与状态，无全局会话
  document_loader.py       # 元数据校验、Markdown 原文加载
  corpus.py                # 只读资料接口及冒烟资料源
  tools.py                 # 框架工具与资料接口适配
  evidence.py              # 本轮证据登记、原文引用校验
  agent.py                 # Agent 装配、指令及引用校验
  output_validation.py     # 结构错误反馈、混合终态拒绝、共享修正额度
  budgets.py               # 模型／HTTP／工具的接纳计数与整轮截止检查
  execution_policy.py      # 框架工具执行钩子、异步超时和取消
  model_adapter.py         # 模型创建、请求记录与有限重试
  mock_model.py            # 显式冒烟脚本
  runtime.py               # 单轮协调、终止及结果保存
  trace.py                 # 运行材料持久化
  retrieval/               # 独立搜索：tokenizer、分块、快照、BM25、分页及工具入口
  reading/                 # 独立读取：全文／章节／块、超限定位分页及工具入口
tests/
  retrieval/               # 内部分 smoke、contract、business
  reading/                 # 内部分 smoke、contract、business、boundary
  agent_loop/              # 内部分 contract、boundary
  integration/smoke/       # CLI、主循环与占位工具接入冒烟
  e2e/                     # 最终完整业务验收，当前仅说明
  support/                 # 共享隔离与材料导出
data/
  smoke/                   # 合成接入资料
  fixtures/                # F1 单规则、F2 冲突、R1 章节补读原文
  prepared/                # 正式 tokenizer 生成的离线块与指纹
examples/
  retrieval/, reading/, agent_loop/, integration/, e2e/
                           # 各自 inputs、outputs、traces、reports，按实际材料建立
```

CLI 和测试复用同一运行器，真实与 Mock 模式复用同一 Agent、工具和证据链。后续可替换资料源、扩展工具契约，不需要复制整套运行流程。

## Git 提交边界

- 提交：`src/`、`tests/`、合成资料及离线所需的预生成块、`examples/` 中的验证材料、文档、`requirements.txt`、`pyproject.toml`、`.python-version` 和 `.env.example`。
- 忽略：真实 `.env`、密钥、虚拟环境、Python／测试缓存、安装及构建产物、编辑器文件；本地模型下载使用 `runtime/models/` 或 `models/`，临时结果使用 `runtime/`，均不提交。
- `examples/` 是考核交付材料，不整体忽略。评估中要求保留的成功、失败及复测记录均须保存；纯开发试跑可以显式写到本地目录：

```sh
PYTHONPATH=src python -m knowledge_agent smoke --mode mock --output-dir runtime/runs
```

`.gitignore` 只影响 Git 收录，不会删除本地文件；已经被 Git 跟踪的文件不会因新增忽略规则自动移出版本管理。

## 未完成范围

当前已通过一次历史真实模型冒烟；六类 Agent 业务验收、至少两条真实差异路径、正式工具接入、向量／混合检索、多轮历史和完整评估器均未完成。简单引用校验仅保证出处与文字一致，不保证结论受引用支持。

当前独立 BM25 搜索与读取工具均已有单工具验证，并直接验证搜索定位到章节／块读取的契约兼容；Agent 仍使用原有占位工具。下一步另行接入主循环并回归。

[PRD](docs/01-requirements.md) · [技术方案](docs/02-solution.md) · [AI 使用记录](docs/04-ai-usage.md)

实际人工投入时长、个人修改与贡献、最终复盘、题号、GitHub 地址和最终 commit SHA 待用户核实及最终交付时填写，不根据 AI 运行时间推测个人工时。
