# 独立检索工具

本目录不依赖 Agent runtime，不调用模型。现有 `knowledge_agent.tools` 仍为主循环冒烟适配器；后续联调时由薄适配层复用本目录，不复制检索逻辑。

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
