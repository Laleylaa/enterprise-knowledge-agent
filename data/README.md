# 知识资料存储契约

所有制度均为合成内容，不代表真实企业制度。正式知识库采用 **Markdown 原文＋元数据清单**；不能把带 body 的 JSON 文档数组作为加载入口。

## 唯一原文与元数据

```text
<资料集>/
  manifest.json
  documents/
    D01.md
```

元数据格式固定为：

```json
{
  "schema_version": 1,
  "documents": [
    {
      "doc_id": "D01",
      "title": "差旅报销规定 D01",
      "version_date": "2026-01-01",
      "source_path": "documents/D01.md"
    }
  ]
}
```

- manifest 使用 UTF-8 JSON；文档清单非空。文档 ID、标题、路径非空，日期为有效 YYYY-MM-DD。ID 和解析后的原文路径在资料集中唯一。
- source_path 使用相对于 manifest 所在目录的 POSIX 路径，只指向该目录内的 `.md` 文件；禁止绝对路径、向上跳转及符号链接越界。
- Markdown 文件是唯一正文来源。元数据不保存 body，不接受未声明字段；本版本不解析 front matter。ID 与版本日期只在清单维护，避免重复事实。
- 正文严格按 UTF-8 解码，不剥离空白、不替换换行、不插入标题。内部 Document.body 等于解码后的完整原文；引用和未来分块的字符偏移以此为准。
- 文档有无章节不影响基础加载；正式制度应使用自然标题、段落和编号条款。无标题的最小资料仅保留作冒烟。
- 加载失败明确报错，不自动回退到旧 JSON 格式或其他资料。

加载组件位于 [document_loader.py](../src/knowledge_agent/document_loader.py)，只负责清单校验与原文读取，组装内部 Document。检索源通过它加载资料；Agent 和工具不解析存储文件。内部对象及实际运行快照仍可序列化为 JSON，这不构成第二套可编辑原文。

## 当前准备状态

| 区域 | 状态与用途 |
|---|---|
| [smoke/manifest.json](smoke/manifest.json) | 最小冒烟资料也采用正式格式；原有单句正文及脚本前提保持不变 |
| [F1 清单](fixtures/F1_single_rule/manifest.json)、[D01 原文](fixtures/F1_single_rule/documents/D01.md) | 已准备一份有章节的制度，包含提交期限及处理状态说明；没有凭证要求 |
| [F2 清单](fixtures/F2_conflicting_rules/manifest.json) | 独立冲突资料：D01 为 30 天，D02 为 15 天；相同日期，不提供优先级或范围解释 |
| [prepared](prepared/README.md) | F1、F2 的正式 tokenizer 预生成块，支持无网络、无 tokenizer 文件的基础搜索 |

F1 和 F2 已用于独立搜索工具的测试，不表示 Q01／Q02 的 Agent 行为已验收，也不是当前固定 Mock 脚本的输入。原有 Agent 冒烟仍只使用 smoke/manifest.json。

已删除旧格式的 F2～F6 条款草稿及提前建立的全量评估索引。后续按实际开发需要逐组编写文档与对应测试；关键条款及冲突、缺口等场景仍以 solution §11.4 为准。

每次只加载一套资料，禁止把互斥场景合并。原有冒烟指纹保持其原有定义；新检索快照的 corpus_hash 包括来源、分块配置和 tokenizer 身份，索引另记录分词字典及 BM25 参数指纹。派生块经过原文位置、覆盖范围和预算检查。预期答案和故障计划不进入知识原文或模型输入。
