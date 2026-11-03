# 企业知识问答 Agent

面向员工制度问答的本地 CLI 项目。模型根据文档检索与原文读取结果选择补查、结束取证或交由回复阶段追问，输出回答、文档 ID 与原文引用、资料缺口和任务状态。全部制度与 FAQ 均为合成资料。

项目采用一个取证 Agent 循环与独立回复模块，支持冲突查证、上下文追问、工具故障处理和有限执行。提供真实模型入口，以及无需密钥的离线 Mock 入口。

## 评审入口

建议先查看评估与实际运行记录，再按下文完成离线运行；配置模型服务后可复跑真实业务验收。

| 检查内容 | 材料入口 |
| --- | --- |
| 用户、范围与成功标准 | [需求文档](docs/01-requirements.md) |
| 调用流程、动态决策、框架职责与技术取舍 | [技术方案](docs/02-solution.md) |
| 六项必验的预期、实际结果及限制 | [测试与评估](docs/03-evaluation.md) |
| 输入、实际输出、Trace 与资料快照 | [运行记录索引](examples/submission-check/cases.md) |
| 模型根据工具结果调整动作的路径 | [动态决策验证](docs/03-evaluation.md#3-两阶段状态与动态决策验证) |
| AI 辅助范围、个人贡献与验证 | [AI 使用说明](docs/04-ai-usage.md) |
| 关键问题、实践收获与改进计划 | [项目复盘](docs/05-retrospective.md) |

正式验收批次为 **54 项通过，0 失败、0 错误、0 跳过**：基础契约 29 项、离线 Mock 7 项、真实业务必验 6 项、真实业务扩展 12 项。材料入口见[批次与索引](examples/README.md#批次与索引)。

按评审目的选择运行入口：

| 使用方式 | LLM 配置 | Embedding 配置 | 操作入口 |
| --- | --- | --- | --- |
| 离线 Mock | 无需密钥，使用固定脚本 | 无需模型资产，使用 BM25 | [离线运行](#离线运行) |
| 真实问答，默认 hybrid 主线 | 配置模型服务与 API 密钥 | 准备本地 BGE 模型 | 按[真实模型运行](#真实模型运行)依次配置、准备和提问 |
| 真实问答，仅 BM25 | 配置模型服务与 API 密钥 | 无需模型资产 | 完成模型服务配置后，使用 `--retrieval bm25` [运行问答](#单次问答与连续对话) |

## 环境与安装

- Python：项目声明支持 3.11～3.12，已验证环境为 **Python 3.11.15 / macOS arm64**。提供 macOS/Linux 与原生 Windows PowerShell 命令；Windows/Linux 未纳入本次实机验证，平台适配检查见[评估文档](docs/03-evaluation.md#4-基础验证与结果核对)。
- 依赖：统一安装 [requirements.txt](requirements.txt)，包括 PydanticAI 2.64.0、OpenAI SDK 3.42.0、检索组件及 pytest。框架承担的职责见技术方案。
- 网络与模型资产：安装依赖需要网络；真实问答需要模型服务。hybrid/vector 首次使用还需下载本地 BGE 资产，推理使用 CPU，无需 GPU。

### macOS / Linux

已安装 Python 3.11 时执行；使用 Python 3.12 时，将创建虚拟环境的命令改为 `python3.12 -m venv .venv`。

```sh
git clone https://github.com/Laleylaa/enterprise-knowledge-agent.git
cd enterprise-knowledge-agent
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONPATH=src
export PYTHONUTF8=1
```

### Windows（原生 PowerShell）

安装 Git 与 64 位 Python 3.11 或 3.12 后，在 PowerShell 执行。使用 Python 3.12 时，将 `py -3.11` 改为 `py -3.12`。无需安装 WSL。

```powershell
git clone https://github.com/Laleylaa/enterprise-knowledge-agent.git
cd enterprise-knowledge-agent
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
$env:PYTHONUTF8 = "1"
```

若 PowerShell 提示禁止执行激活脚本，可先执行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`，再重新激活；该设置仅作用于当前 PowerShell 会话。

两种平台已有仓库时均从创建虚拟环境开始。后续命令均在仓库根目录、已激活的虚拟环境中执行，使用同一个 `python -m knowledge_agent` 入口。`PYTHONPATH` 用于直接加载源码，`PYTHONUTF8` 统一中文文件与日志编码；重新打开终端后需重新激活环境并设置这两个变量。下方运行命令使用单行形式，可直接用于上述两种终端。

## 离线运行

无需创建 `.env`、填写密钥或下载 tokenizer / 向量权重。依赖安装完成后，使用仓库预生成的检索块即可离线运行。

### 单次问答

```sh
python -m knowledge_agent chat --mode mock --retrieval bm25 --scenario normal --corpus data/fixtures/F1_single_rule/manifest.json --prepared data/prepared/F1_single_rule.json --question "国内差旅报销期限多久？" --output-dir examples/evaluation/mock-chat
```

预期显示“已解决”，回答国内差旅行程结束后 30 天内提交，并列出 D01 原文与版本日期。任务状态旁会标明离线 Mock 的验证边界。

### 正常、资料不足与工具失败等场景

```sh
python -m knowledge_agent evaluate --mode mock --retrieval bm25 --output-dir examples/evaluation/mock
```

该命令运行 7 项离线测试，覆盖正常、冲突、缺资料、工具失败、故障恢复、预算停止及不支持的输入；预期汇总为 `status: passed`、`passed: 7`。终端会给出本批材料目录，其中保存测试日志、汇总、JUnit 结果及各次运行记录。

单次 `chat` 也可使用以下固定脚本；替换 `--scenario`、`--question`，并成对选择对应资料路径。

| scenario | 固定问题 | 资料目录／预生成块 | 预期任务状态 |
| --- | --- | --- | --- |
| normal | 国内差旅报销期限多久？ | F1_single_rule | resolved |
| conflict | 差旅报销期限多久？ | F2_conflicting_rules | needs_info |
| missing | 请查阅 D99 的规定。 | F1_single_rule | unresolved |
| tool_failure | 国内差旅报销期限多久？ | F1_single_rule | incomplete |
| recovery | 国内差旅报销期限多久？ | F1_single_rule | resolved |
| budget | 国内差旅报销期限多久？ | F1_single_rule | incomplete |

资料路径格式为 `data/fixtures/<资料目录>/manifest.json` 与 `data/prepared/<资料目录>.json`。Mock 实际执行检索、读取和预算控制，但模型响应为固定脚本，**只验证流程，不证明真实模型决策效果**；不支持任意问题，也不会在真实模式故障时自动启用。

## 真实模型运行

### 配置模型服务

首次配置时复制配置模板：macOS/Linux 执行 `cp .env.example .env`；Windows PowerShell 执行 `Copy-Item .env.example .env`。

在本机 `.env` 中填写 `DEEPSEEK_API_KEY`。已有 `.env` 时直接编辑，保留自己的配置。默认模型为 `deepseek-flash`，服务地址为 `https://api.deepseek.com`；可通过 `KA_MODEL_NAME`、`KA_BASE_URL` 调整。真实调用会使用所配置账户的 API 额度，`.env` 已被 Git 忽略。

默认主线使用两类模型，职责与配置如下：

| 组件 | 职责 | 配置方式 |
| --- | --- | --- |
| 远程 LLM | 决定工具动作、判断证据状态并生成回答 | 在 `.env` 填写 `DEEPSEEK_API_KEY`；`KA_MODEL_NAME`、`KA_BASE_URL` 默认已配置 |
| 本地 embedding 模型 | 将查询和文档块编码为向量，参与 hybrid 检索 | 使用固定版本 `BAAI/bge-small-zh-v1.5`；由下方准备命令下载，无需额外 API 密钥或部署服务 |

沿用默认方案时，只需手动填写 LLM 密钥，再执行一次资产准备命令。embedding 模型默认保存到 `runtime/models/bge-small-zh-v1.5`，可通过 `.env` 中的 `KA_EMBEDDING_MODEL_PATH` 指向已准备的同版本资产；`KA_TOKENIZER_PATH` 指定分块 tokenizer 文件，`KA_RETRIEVAL_CACHE_DIR` 指定检索缓存目录。模型文件会按固定版本校验，这些路径配置不用于任意替换 embedding 模型。

配置优先级为 **CLI 参数 > 系统环境变量 > .env > 默认值**。完整变量见 [.env.example](.env.example)。

### 准备本地检索资产

默认真实检索为 hybrid（BM25 与本地向量融合）。首次运行需要访问 Hugging Face 下载固定版本的 BGE-small-zh-v1.5 模型与 tokenizer 资产，命令如下：

`runtime/` 保存本地模型、缓存和日常自由问答记录，不随仓库提交。首次克隆后该目录不存在是正常情况；下方命令会按 `.env` 中配置的路径创建目录并准备资产，无需手动创建。已提交的 `data/prepared/` 是检索块，不包含 embedding 模型权重。

```sh
python -m knowledge_agent prepare --mode real --retrieval hybrid --download --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json --output-dir runtime/preparation
```

成功时输出 `status: prepared`，`effective_branches` 包含 `bm25` 和 `vector`。`prepare` 不调用问答模型；后续资产齐备时可省略 `--download`。若返回 `partial`，说明部分检索分支不可用，应根据 `errors` 修复后再验证完整 hybrid。

### 单次问答与连续对话

```sh
python -m knowledge_agent chat --mode real --retrieval hybrid --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json --question "国内差旅报销期限多久？" --output-dir runtime/chat
```

去掉 `--question` 进入连续对话，可继续提问“需要哪些凭证？”，输入 `/exit` 退出。增加 `--format json` 可查看结构化结果。

该入口加载 8 份[业务制度与 FAQ](data/README.md#业务资料)，覆盖差旅、凭证与补交、请假、设备借用和账号权限。业务资料提供场景素材；测试使用按验收条件整理的独立 fixtures。

若只使用 BM25，将问答命令中的 `--retrieval hybrid` 改为 `--retrieval bm25`，可直接使用预生成块，跳过本地模型资产准备；问答仍调用真实模型。`vector` 只使用本地向量检索，需要先准备模型资产。

`--history history.json` 可导入如下格式的历史文件：

```json
{"schema_version":1,"messages":[{"role":"user","content":"我想了解国内差旅报销。"},{"role":"assistant","content":"请说明需要查询的事项。"}]}
```

历史用于理解指代和用户条件。当前会话取得的原文经版本核验后可在后续问题中复用；导入历史只恢复文本，不恢复原文证据。

### 输出与运行记录

文本输出包含任务状态、回答与必要追问、引用和资料缺口。单题运行的退出码如下：

| 状态或情况 | 含义 | 退出码 |
| --- | --- | --- |
| resolved | 已解决 | 0 |
| needs_info | 待补充信息，附具体追问 | 0 |
| unresolved | 资料不足、冲突未解或超出范围 | 0 |
| incomplete | 必要处理因故障或执行上限中断 | 1 |
| 输入、配置或文件处理错误 | CLI 报错 | 2 |
| 用户中断 | 取消本次执行 | 130 |

每轮问答材料保存到 `<输出目录>/<real或mock>/<run_id>/`，包含 `input.json`、`output.json`、`trace.jsonl` 及原文和调用记录；会话材料另存于 `<输出目录>/<real或mock>/sessions/<session_id>/`。

每轮默认最多 10 次模型调用、16 次业务工具调用，处理时限 120 秒，不含事先资料准备和索引初始化。硬中断返回 `incomplete`；检索单分支降级则由模型根据已有原文判断能否回答，具体错误记录在 Trace 中。完整规则见[会话与执行控制](docs/02-solution.md#5-会话与执行控制)。

## 测试与复现

### 无真实模型调用的检查

```sh
python -m pytest tests -q --examples-dir examples/evaluation/offline --junitxml=examples/evaluation/offline-results.xml
```

预期 **36 项通过、18 项跳过**：29 项基础契约与 7 项 Mock 执行，18 项真实业务测试需显式启用。此命令的通过结果不等于全部真实业务验收通过。

### 真实业务验收

完成密钥配置和 hybrid 资产准备后运行：

```sh
# 仅收集：不调用模型，不计为通过
python -m knowledge_agent evaluate --mode real --retrieval hybrid --collect-only --output-dir examples/evaluation/collect

# 执行六项必验与十二项扩展业务测试
python -m knowledge_agent evaluate --mode real --retrieval hybrid --run-live --output-dir examples/evaluation/real
```

`evaluate` 自动使用每个用例规定的资料，不接受 `--corpus`、`--prepared` 覆盖。可增加 `--suite tests/e2e/required` 只跑六项必验，或用 `-k` 筛选名称。完整业务验收使用 hybrid；两项检索降级专项在其他检索模式下跳过，跳过不算完整通过。

评估输出包含材料目录与通过、失败、错误、跳过计数。真实模型的措辞和动作可能变化，自动检查通过后仍需结合原文核对答案含义与引用支持关系。

[完整复跑与打包步骤](examples/README.md#完整复跑与打包)说明如何合并基础、Mock 和真实业务结果，生成包含输入、实际输出、精简 Trace 与共用资料快照的提交包。已有提交材料可直接阅读，无需先运行测试。固定 Mock 与测试用例的复跑材料写入 `examples/evaluation/`，正式验收材料集中在 `examples/submission-check/`；日常从 `chat` 入口自由提问的记录写入 `runtime/`。评审不依赖本地开发归档。

## 项目结构

```text
README.md                       环境、安装、运行与评审导航
requirements.txt                固定依赖版本
.env.example                    配置变量示例
src/knowledge_agent/             Agent、模型接入、工具与 CLI
  retrieval/                    检索工具
  reading/                      原文读取工具
tests/
  contracts/                    基础契约检查
  e2e/required/                 六项必验业务
  e2e/extended/                 十二项扩展业务
  e2e/offline/                  七项离线流程检查
data/
  knowledge_base/               日常业务资料
  fixtures/                     独立验收资料
  prepared/                     预生成检索块
examples/submission-check/      实际验收结果与运行记录
docs/
  01-requirements.md             需求
  02-solution.md                 方案
  03-evaluation.md               评估
  04-ai-usage.md                 AI 使用
  05-retrospective.md            复盘
```

资料用途与维护见 [data/README.md](data/README.md)，工具职责与独立调用见[技术方案](docs/02-solution.md#42-检索和读取工具)，验证材料与打包步骤见 [examples/README.md](examples/README.md)。

## 提交与版本定位

所选题目为**第三题 — 企业知识问答 Agent**，仓库地址为 [Laleylaa/enterprise-knowledge-agent](https://github.com/Laleylaa/enterprise-knowledge-agent)。评审可在检出的仓库中执行以下命令确认版本，并与提交时提供的 commit SHA 核对：

```sh
git rev-parse HEAD
```

个人贡献与验证说明以 [AI 使用说明](docs/04-ai-usage.md)为准，完成情况与后续计划见[项目复盘](docs/05-retrospective.md)，当前效果和验证限制见[评估文档](docs/03-evaluation.md)。
