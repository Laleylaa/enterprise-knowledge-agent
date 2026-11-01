# 企业知识问答 Agent

当前阶段：**最小工程底座与端到端冒烟**。已具备 CLI → PydanticAI → 本地工具 → 结构化结果 → 文件记录的运行链路。

目前使用 `data/smoke/manifest.json` 的小型合成资料。`search_knowledge` 返回这份资料集的全部候选，明确标记 `smoke_fixture`，**尚未实现 BM25、向量或混合检索**。此入口用于验证接入，不代表完整企业知识问答产品。

知识库统一采用 [Markdown 原文＋元数据清单](data/README.md)，保留最小冒烟资料及一份 F1 制度样例。Q01～Q18 目前仅是 solution 中的验收计划，后续随功能实现逐项补充资料和测试，不预先铺开全部用例。

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

### 离线冒烟

```sh
PYTHONPATH=src python -m knowledge_agent smoke --mode mock
```

不需要密钥、模型权重或运行时网络；首次安装依赖仍需网络或本地安装包。Mock 仅支持固定问题“国内差旅报销期限多久？”和当前冒烟资料。它使用预设模型脚本调用真实本地工具，不证明真实模型决策效果，也不是 solution 中的完整 Mock 场景集合。

标准输出为 JSON，包含回答、引用、缺口、状态、真实／Mock 模式、来源标记、计数及已取得原文；材料目录写到标准错误。正常离线运行应有两次脚本决策、一次业务工具调用、零次 HTTP 尝试。

日常试跑默认保存到被 Git 忽略的 `runtime/runs/`。需要留作开发测试证据时，显式指定分类目录：

```sh
PYTHONPATH=src python -m knowledge_agent smoke --mode mock --output-dir examples/tests/smoke/runs
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

主要配置见 `.env.example`：模型、资料及输出路径、模型轮次、HTTP 尝试、工具次数、输出修正、单次及整轮超时。基础上限已接入；精确边界、混合响应和异常重试等仍待后续契约验证。当前只有 `smoke` 与 `config` 命令，solution 规划的 `chat / prepare / evaluate` 尚未提供。

退出码：0 表示本轮正常交付（包括正常的未解决／待补充）；1 表示未完成；2 表示配置、输入或材料读写失败；130 表示用户中断。

## 测试与评审入口

```sh
# 本阶段全部冒烟；真实 API 用例默认跳过
python -m pytest tests/smoke -q --junitxml=examples/tests/smoke/reports/scope-aligned-smoke-results.xml

# 配好本机密钥后，显式执行真实模型冒烟
python -m pytest tests/smoke/test_live.py --run-live -q
```

所有测试按目的分类，详见 [tests/README.md](tests/README.md)。本阶段仅编写和执行冒烟测试，契约测试与业务验收留到后续阶段。

开发测试材料位于 `examples/tests/`，用于检查程序是否正确；业务正常流、异常流的输入、实际输出及行动过程位于 `examples/traces/`，用于核对 Agent 行为与结果。当前业务验证目录只有规范说明，尚无验收记录。完整索引见 [examples/README.md](examples/README.md)。

- [本阶段评估与限制](docs/03-evaluation.md)
- [当前冒烟：5 passed，1 skipped](examples/tests/smoke/reports/scope-aligned-smoke-results.xml)
- [初始冒烟：5 passed，1 skipped](examples/tests/smoke/reports/smoke-results.xml)
- [显式真实模型冒烟：1 passed](examples/tests/smoke/reports/live-smoke-network-results.xml)；[实际输出](examples/tests/smoke/runs/real/2f49173f9b8540b8af130a1e735b8430/output.json)。首次受限环境连接失败的记录另见评估文档。
- [离线冒烟实际输出](examples/tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/output.json)
- [离线冒烟 Trace](examples/tests/smoke/runs/mock/7882cbd51ad8437e9901d74fa081be6b/trace.jsonl)
- [真实模式缺少密钥的中断记录](examples/tests/smoke/runs/real/b31b71e307f14fbe980e1843cb1f7712/output.json)：没有发送真实 API 请求，不能作为真实模型效果证据。

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
  agent.py                 # Agent 装配、指令及输出校验
  model_adapter.py         # 模型创建、请求记录与有限重试
  mock_model.py            # 显式冒烟脚本
  runtime.py               # 单轮协调、终止及结果保存
  trace.py                 # 运行材料持久化
tests/
  smoke/                   # 启动、配置与端到端冒烟
data/
  smoke/                   # 合成接入资料
  fixtures/                # 一份 F1 制度样例，尚未业务验收
examples/
  traces/                  # 业务正常流、异常流验证；尚未生成记录
  tests/smoke/reports/      # 开发阶段冒烟测试报告
  tests/smoke/runs/         # 冒烟输入、输出和调试 Trace，按模式和运行 ID 分组
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

当前已通过一次真实模型冒烟；六类业务验收、至少两条真实差异路径、完整工具协议、分块与检索、多轮历史、完整故障注入和评估器均未完成。简单引用校验仅保证出处与文字一致，不保证结论受引用支持。

当前交付只完成底座与端到端冒烟，另保留 F1 原文样例，不宣称 solution 第 13 节第一阶段的全部接入检查完成。下一步按确认的阶段补齐契约验证及基础检索。

[PRD](docs/01-requirements.md) · [技术方案](docs/02-solution.md) · [AI 使用记录](docs/04-ai-usage.md)

实际人工投入时长、个人修改与贡献、最终复盘、题号、GitHub 地址和最终 commit SHA 待用户核实及最终交付时填写，不根据 AI 运行时间推测个人工时。
