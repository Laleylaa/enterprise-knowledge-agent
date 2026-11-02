# 独立检索工具

本目录不依赖 Agent runtime，不调用主模型。BM25 不加载神经网络；vector 在受控子进程中加载本地 BGE。hybrid 按等权 RRF 融合两支。`tool_binding.py` 已通过标准函数工具注册复用三种模式，异步路径直接等待可取消计算。`knowledge_agent.tools` 的旧函数只保留作原 smoke_fixture 适配器，不复制检索逻辑。

独立 CLI 已支持 `download-model`、`prepare --retrieval vector` 和 `search --retrieval vector`；命令见 [根 README](../../../README.md)，实际验证见 [向量记录](../../../docs/03-evaluation.md)。`model_assets.py` 固定资产与校验，`embedding_worker.py` 管理可终止计算，`vector.py` 管理向量身份／缓存／排名，`backend.py` 定义内部后端协议与带分支状态的排名结果；`hybrid.py` 融合排名，`factory.py` 统一构建三种索引。对外 SearchRequest 字段不变，execution 明确记录 requested_mode 和 effective_branches。

向量工具须用上下文管理器或 close 释放进程；异步调用使用 VectorIndex.arank／EmbeddingWorker.aencode，不在事件循环内调用同步 rank／encode。超时或取消会回收 worker；新请求重新启动，不自动重做失败请求。正常查询不下载权重，vector 错误不改成 BM25。冷启动、建索引、编码分别有配置时限；终止和回收另有有界等待。

| 组件 | 职责 |
|---|---|
| `tokenizer.py` | 只加载本地固定 tokenizer；显式下载命令校验 SHA-256 |
| `chunking.py` | ATX Markdown 标题、围栏代码识别；原文位置、段落／句子／token 窗口分块 |
| `snapshot.py` | 原文一致快照、派生块校验、过期重建与正文预算检查 |
| `bm25.py` | jieba 一致分词、BM25Okapi 排名、词项重合候选及精确 ID 查找 |
| `tool.py` | 完整 BM25 搜索参数、错误、游标、返回预算、证据登记及记录 |
| `session.py` | 单工具装配与运行材料，明确 model_calls=0 |
| `__main__.py` | 独立 download-tokenizer／prepare／search 命令 |

可复用调用方式（从仓库根目录，环境中已安装项目或设置 PYTHONPATH=src）：

```python
from pathlib import Path
from knowledge_agent.config import Settings
from knowledge_agent.retrieval.session import create_search_tool

settings = Settings(_env_file=None, output_dir=Path("runtime/search-tool"))
tool = create_search_tool(
    settings,
    Path("data/fixtures/F1_single_rule/manifest.json"),
    Path("data/prepared/F1_single_rule.json"),
)
arguments = {"query": "报销期限", "purpose": "查找原文", "limit": 1}
first = tool.execute(arguments, call_id="search-1")
cursor = first["execution"]["next_cursor"]
if cursor:
    second = tool.execute({**arguments, "cursor": cursor}, call_id="search-2")
```

公开参数由 SearchRequest 定义，`model_json_schema()` 可供后续框架适配；call_id 由调用方传入，不属于模型参数。query 非空，或以空 query＋明确 doc_ids 定位。purpose 只记日志，不参与排序。每页 1～10 块；重复 doc_ids 按首次出现去重。

游标保存在当前工具实例内，固定候选排名，并绑定工具、快照、索引版本、原查询、过滤、limit 和正文预算；翻页不重新执行排名。实例结束后失效，不支持跨进程续页或任务恢复。内存最多保留配置数量的游标，超额淘汰最早项；使用失效值返回 INVALID_CURSOR。每个并行请求应使用各自工具实例和证据集合。

搜索状态仅为 ok／empty／partial／error。缺失部分 ID 时仍返回有效部分，并持续报告 NOT_FOUND；排名失败返回 SEARCH_FAILED，不降级为全库返回。BM25 只要求词项重合，不以分数正负排除匹配候选；使用全快照词频统计，在过滤范围内选取并排序候选，分数并列按块 ID 固定次序。

返回完整原文块，标题与正文分别具有真实位置；分离的标题不会与正文拼接成可引用段。EvidenceStore.add_excerpt 复用原证据组件，记录实际返回的来源片段，原整篇 add 接口保留。此阶段没有向模型发送结果，交付单工具记录中 delivered_to_model=false。

分块默认目标 320／硬上限 480／重叠最多 48 tokens，含索引标题上下文和特殊 token。使用实际 BGE tokenizer；只对索引标题上下文取前缀并记录 context_truncated，原文与返回标题不截断。无标题文档使用 ROOT；目前识别 ATX 标题和围栏代码，不宣称完整 Markdown AST 支持。配置、内容和 tokenizer 身份纳入块指纹，分词字典及 BM25 参数纳入索引指纹。

BM25 索引每次启动从已校验的块重建，不持久化排名索引，避免误用旧索引；派生块文件可缓存。正文预算至少容纳每个块及所属标题，启动时检查；调用层另有 RETURN_BUDGET_TOO_SMALL 防御。当前组件同步执行，未在这里扩展 Agent 超时策略或 CPU worker。

每次执行保存 input/output、tool-inputs/tool-results、Trace 及已有证据；多次调用时 JSONL 保留完整过程，input.json/output.json 为最后一次调用。run.json 标识单工具来源，corpus.json 和 index-manifest.json 保留版本。记录与证据写入失败显式抛出，不把未保存的材料当成功交付。

以上为 standalone=True 的独立入口。Agent 绑定时使用 standalone=False，共享当轮 EvidenceStore／RunRecorder，保留工具 JSONL 和证据，跳过工具层 input/output 写入及 tool_started 事件（由运行器和执行钩子分别负责）。游标实例跨同轮模型请求保留，每个新问题重新创建。接入测试见 [FC 记录](../../../docs/03-evaluation.md)。

## 三模式集成约定

`Settings.selected_retrieval` 统一解析显式配置与 real=hybrid／mock=bm25 默认。`create_search_tool` 和 `IndexedCorpus` 共用构建入口；正常 Agent 会话复用索引，逐轮新建工具、证据与游标。向量／混合工具使用 `aexecute(deadline=...)`，工具与整轮中较早的 deadline 生效，并预留 terminate／kill 回收时间。

RRF 对完整分支排名按 rank 从1开始累加 `1/(k+rank)`，默认 k=60；相同块去重、不同文档来源不合并。失败分支不贡献排名但保留错误，成功空分支也列入 effective_branches。分页冻结候选、错误及分支列表。初始化失败的分支在本索引生命周期持续缺席；修复本地资产后需重新启动。

`open_indexed_source` 由 CLI 使用，负责 finally 关闭及独立生命周期记录；嵌入式调用方使用 `with IndexedCorpus.load(...)` 或显式 close。组件验证与实际小样本比较见 [阶段索引](../../../docs/03-evaluation.md)，不代替真实主模型业务验收。
