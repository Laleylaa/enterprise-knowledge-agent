# 企业知识问答 Agent

面向员工制度问答的CLI项目。取证Agent根据检索和原文读取结果动态补查或停止；独立回答阶段接收程序交付的原文，按段落选择证据ID。程序展开真实引用，输出自然语言回答、文档ID与原文、资料缺口和任务状态。全部制度为合成资料。

**评审入口：** [需求](docs/01-requirements.md) → [设计](docs/02-solution.md) → [测试结果与覆盖](docs/03-evaluation.md) → [实际输入、输出和Trace](examples/README.md)。[AI使用记录](docs/04-ai-usage.md)与[复盘](docs/05-retrospective.md)单独维护。

## 安装

Python 3.11（项目声明支持3.11～3.12），本地验证环境为macOS arm64。依赖集中固定在requirements.txt，PydanticAI负责标准工具调用循环。

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

以下命令从仓库根执行；无需先安装项目本身。可选 `python -m pip install -e .` 后使用 `knowledge-agent`。

## 离线Mock：无需模型密钥和本地向量权重

```sh
PYTHONPATH=src python -m knowledge_agent chat --mode mock --retrieval bm25 --scenario normal \
  --corpus data/fixtures/F1_single_rule/manifest.json \
  --prepared data/prepared/F1_single_rule.json \
  --question "国内差旅报销期限多久？" --format json --output-dir runtime/offline

PYTHONPATH=src python -m knowledge_agent evaluate --mode mock --retrieval bm25 \
  --output-dir runtime/evaluation/mock
```

依赖安装后可完全离线运行，使用仓库预生成块。Mock只使用BM25，模型响应是固定脚本，工具和运行器实际执行；它只验证流程，不证明真实模型决策。

| scenario | 固定问题与资料 | 行为 |
| --- | --- | --- |
| normal | 国内差旅报销期限多久？／F1 | 搜索原文并引用 |
| conflict | 差旅报销期限多久？／F2 | 读取并保留冲突 |
| missing | 请查阅 D99 的规定。／F1 | 原文不存在 |
| tool_failure | 国内差旅报销期限多久？／F1 | 注入读取失败 |
| recovery | 同上／F1 | 搜索失败后脚本改读原文 |
| budget | 同上／F1 | 实际预算守卫停止，返回incomplete |

Mock不支持任意问题；不匹配的输入明确拒绝。真实模式不会因模型失败而静默切换Mock。

## 真实入口：默认hybrid

从 `.env.example` 复制本地 `.env` 并填写 `DEEPSEEK_API_KEY`。密钥不提交。`KA_MODEL_NAME` 默认deepseek-flash，可在本地配置。首次准备hybrid资产需显式允许下载：

```sh
PYTHONPATH=src python -m knowledge_agent prepare --retrieval hybrid --download \
  --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json

PYTHONPATH=src python -m knowledge_agent chat --mode real \
  --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json \
  --question "国内差旅报销期限多久？" --format json --output-dir runtime/chat
```

以上真实入口使用独立的[业务知识库](data/knowledge_base/README.md)（8份合成制度与FAQ：差旅、凭证与补交、请假、设备借用、账号权限）。专项验收仍使用固定 fixtures，Mock仍使用对应脚本资料；原有真实运行记录不代表扩充后资料的新一轮验收；新增专项验证保存在local_validation。

去掉 `--question` 进入连续对话，`/exit` 退出。`--history` 可显式导入 `{"schema_version":1,"messages":[{"role":"user","content":"此前的问题"},{"role":"assistant","content":"此前的回答"}]}` 文件。历史用于理解指代；同一会话内已取得的原文经资料版本核验后可复用，资料变化或依据不足时重新取证。导入历史不恢复原文证据。

默认文本展示仅含任务状态、回答（含必要追问）、引用及资料缺口；引用保留文档ID、版本日期与原文。离线Mock在任务状态旁注明流程验证边界。内部结束原因、证据ID、字符位置、工具执行与检索降级信息保留在 `--format json` 的结果或输出目录的Trace中，不逐项打印到问答终端。

真实模式默认hybrid，可显式 `--retrieval bm25` 或 `--retrieval vector`。配置优先级：CLI > 系统环境 > .env > 默认。`KA_RETRIEVAL_MODE` 属于显式配置。Mock若继承vector/hybrid配置会在启动前报错，可用 `--retrieval bm25` 覆盖。

hybrid某一分支失败时保留有效分支原文，Trace记录partial和具体错误。证据充分可回答；缺范围时由模型继续取证。完整hybrid主线需要本地BGE权重；只有BM25有效的记录必须标明降级，不能当作完整双分支运行。

`prepare` 不调用主模型；已有预生成块的BM25问答无需tokenizer或权重。不要手改派生块，原文变化后用prepare重新生成，详见[资料说明](data/README.md)。

## 测试与交付边界

```sh
# 默认不调用真实模型：24项基础检查 + 7项Mock，18项live跳过
python -m pytest tests -q
# 只收集真实业务，不执行模型
PYTHONPATH=src python -m knowledge_agent evaluate --mode real --collect-only --output-dir runtime/evaluation/collect
# 18项真实业务：6项题目必验 + 12项重要补充
PYTHONPATH=src python -m knowledge_agent evaluate --mode real --run-live --output-dir runtime/evaluation/real
```

`evaluate --suite tests/e2e/required` 可只跑必验，`tests/e2e/extended` 可只跑补充，`-k` 过滤名称。真实默认收集这两个目录并排除offline，Mock只接受offline。基础模块/工具/连接检查独立在 `tests/contracts/`，不替代业务验收。

```text
src/                    产品代码与模型、工具接入
data/                   合成原文、版本元数据与预生成块
tests/
   e2e/required/         六类必验业务
   e2e/extended/         重要补充业务
   e2e/offline/          正式Mock流程
   contracts/           少量基础模块、工具与连接检查
   support/             提交版共用辅助代码
examples/
   submission-check/    精简验收包：测试结果、每轮输入/输出/Trace、共用资料
docs/                   需求、设计、评估、AI使用、复盘
local_validation/       Git忽略：完整开发回归与历史证据
```

`tests/`、`examples/` 已解除整体忽略，提交版不依赖 `local_validation/`。后续临时运行建议写入runtime，避免混入提交证据。提交包含输入、实际输出、精简Trace、共用资料和JUnit结果；不把自动通过或Mock脚本当成语义验收。

当前代码完整重跑49项测试：49项通过、0失败、0错误、0跳过。基础24项、Mock7项、必验真实业务6项及扩展真实业务12项全部通过。本批23轮真实输出及28条引用已进行AI辅助阅读，见[完整报告](examples/submission-check/README.md)、[全部运行记录](examples/submission-check/cases.md)。4个冲突与适用关系用例另各固定复测3次，12次全部通过，见[定向复测](examples/submission-check/repeat-check/README.md)。取证阶段以conflict报告未解冲突，回复阶段独立判断最终状态；测试预期、实际结果与已知限制见[评估](docs/03-evaluation.md)。

通知追问保留跨轮原文及双方引用，返回冲突未解，详见[评估](docs/03-evaluation.md)。

`pytest --examples-dir` 与 `evaluate` 共用精简导出逻辑。运行时完整日志用于测试和本地排查；每轮提交材料仅保留输入、实际输出及Trace，资料按版本共用。完整复跑及打包命令见[材料说明](examples/submission-check/README.md)。已有批次也可直接打包，不重新调用模型：

```sh
PYTHONPATH=src .venv/bin/python -m knowledge_agent.submission --source runtime/evaluation/new-batch --output examples/new-submission
```

examples保留当前版本的完整回归及定向复测精简包；历史批次与完整调试材料留在本地，评审入口不依赖本地文件。

## 提交信息与未完成项

- 所选题：企业知识问答 Agent；正式题号待本人确认。
- GitHub URL、最终commit SHA、实际个人投入时长：待本人填写。代码已分批本地commit，尚未push，最终SHA以完整提交收尾后为准。
- 个人修改、学习收获需本人核实；AI辅助阅读不等于独立人工签署。
- 当前结果与已知缺陷以[评估文档](docs/03-evaluation.md)为准，小型合成资料和有限样本不证明生产可靠性。
