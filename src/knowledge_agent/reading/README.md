# 独立原文读取工具

本组件实现 solution §5.3，不导入或执行 Agent。正式接入由 `tool_binding.py` 的标准函数工具注册完成；原 `tools.py` 冒烟读取继续供 smoke_fixture 使用。

## 调用与来源契约

`ReadRequest.model_json_schema()` 提供公开参数：doc_id、purpose、section_id、chunk_id、cursor。doc_id 和 purpose 必填；section_id 与 chunk_id 互斥。call_id 由调用方提供，不属于模型参数。

| 选择器 | 返回内容 |
|---|---|
| doc_id | 全文按现有 Section 原文顺序分段；拼接 segments.text 恰为原始正文 |
| doc_id＋section_id | 该章节标题及正文 |
| doc_id＋chunk_id | 精确块正文及所属标题，不自动扩展到章节 |

复用 `RetrievalSnapshot`、原文字符偏移、章节／块 ID、`EvidenceStore` 和 `RunRecorder`。读取不重新检索、不判断制度含义或优先级。搜索命中的定位参数可以直接用于读取；两个工具可由调用方共享快照、证据集合和 recorder。单工具装配器则新建独立运行，与 Agent 无关。

```sh
PYTHONPATH=src python -m knowledge_agent.reading \
  --corpus data/fixtures/F1_single_rule/manifest.json \
  --prepared data/prepared/F1_single_rule.json \
  --doc-id D01 --output-dir runtime/read-tool

# R1 的期限块位于同一章节，后面的块另有适用范围
PYTHONPATH=src python -m knowledge_agent.reading \
  --corpus data/fixtures/R1_section_context/manifest.json \
  --prepared data/prepared/R1_section_context.json \
  --doc-id D10 --section-id D10-S0002 --output-dir runtime/read-tool
```

已准备的固定资料读取不需要密钥、模型权重、tokenizer 文件或网络。修改原文后沿用检索模块的显式 prepare 流程；本地 tokenizer 齐备时可重建过期块，否则拒绝启动。组件不下载依赖或文件。

## 超限与错误

读取返回统一工具信封，data 固定有 hits、segments、locators；读取只填 segments，超大对象只填 locators。requested_mode=null，effective_branches=[]。成功是 ok；本组件的单目标读取失败是 error，没有可成功返回的部分时不制造 partial 或 empty。

正文预算与搜索一致，按返回各段 text 和 section_heading 的字符数求和，包含重复出现的标题字段。全文／章节超限返回 CONTENT_TOO_LARGE、空 segments 和局部块定位，不截断正文。每页最多 20 个 locator，read_args 只含 doc_id、chunk_id；调用者另加 purpose 读取正文，不携带定位游标。定位项不是证据。

游标仅用于同一选择器的定位列表续页，翻页仍是 CONTENT_TOO_LARGE，不宣称全文已读完。游标绑定快照、工具、选择器、正文预算和页大小，只在当前实例有效；默认最多 256 项，配置 KA_READ_CURSOR_CAPACITY，超额淘汰最早项。不能跨工具、跨实例、跨快照使用。单次 CLI 只执行一次调用；续页使用同一实例：

```python
from pathlib import Path
from knowledge_agent.config import Settings
from knowledge_agent.reading.session import create_read_tool

settings = Settings(_env_file=None, max_tool_chars=340, output_dir=Path("runtime/read-tool"))
reader = create_read_tool(settings, Path("data/fixtures/R1_section_context/manifest.json"),
                          Path("data/prepared/R1_section_context.json"))
args = {"doc_id": "D10", "section_id": "D10-S0002", "purpose": "核实期限适用范围"}
result = reader.execute(args, call_id="read-section")
if result["execution"]["next_cursor"]:
    page = reader.execute({**args, "cursor": result["execution"]["next_cursor"]}, call_id="locator-page")
if result["data"]["locators"]:
    local = reader.execute({**result["data"]["locators"][0]["read_args"], "purpose": "读取局部原文"}, call_id="read-chunk")
```

未知 ID 返回 NOT_FOUND；存在但属于其他文档的章节／块返回 INVALID_ARGUMENT；无效游标返回 INVALID_CURSOR。实际来源访问异常返回 READ_FAILED，不暴露原始异常内容，不自动重试，不伪造正文。启动时拒绝无法容纳单块及标题的配置；调用时另有 RETURN_BUDGET_TOO_SMALL 防御，避免“读块仍让读同一块”的循环。材料写入失败直接传播，不伪装成业务工具已成功。

## 证据、记录与范围

标题与块正文分别保留真实位置，不拼接不连续片段作为一条引文。实际返回的正文才登记证据，记录调用 ID、快照、版本、来源；读取失败和定位列表不会生成证据。单工具运行没有向模型投递，delivered_to_model=false。

与现有搜索入口一致，多次调用的 input.json/output.json 是最后一次调用，tool-inputs.jsonl/tool-results.jsonl 和 Trace 保留全过程。run.json 标明 standalone_read_tool、model_calls=0；corpus.json 保留原文及派生块。评估通过统一导出器保存到 examples/reading 的 inputs、outputs、traces、reports，以 case_id/run_id 关联。

正式 Agent 绑定使用 standalone=False，共享本轮快照、证据和 recorder，跳过独立入口 input/output 写入以及工具开始事件；运行器保存整轮材料，执行钩子记录开始。原文返回和证据登记逻辑复用本组件；接入测试见 [FC 记录](../../../examples/integration/tool-calls.md)。章节范围沿用现有 ATX 标题切分的 Section，不新增 Markdown 章节树。同步内存读取不包含模型决策、强制异步中断或大规模文件系统性能验证。
