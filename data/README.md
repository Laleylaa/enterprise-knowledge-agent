# 合成资料分类与使用

所有制度均为合成内容。资料按业务用途区分，Markdown正文是唯一可编辑的知识原文。

```text
data/
  knowledge_base/        日常真实问答：差旅、凭证与补交、请假、设备借用、账号权限
    manifest.json
    documents/
  fixtures/              固定专项测试场景，逐套加载
    F1_single_rule/       正常、改写、上下文、部分信息缺失
    F2_conflicting_rules/ 无法消解的期限冲突
    F2_newer_D02/         日期较新但无优先级依据
    F3_explicit_scope/    明确国内／海外范围的基础资料
    F4_scope_evidence/    跨文档说明适用关系
    F5_leave_and_scope/   多主题、资料外问题、条件更正
    F6_replaced_rule/     原文30天改20天
    R1_section_context/  长章节读取边界，兼用于降级业务测试
  smoke/                 最小接入冒烟，非业务验收库
  prepared/              原文的预生成检索块，不是另一套制度
```

| 使用目的 | 入口 | 注意事项 |
| --- | --- | --- |
| 日常真实问答 | [业务知识库](knowledge_base/README.md) | README推荐入口，真实检索默认hybrid；可显式选BM25或vector |
| 题目必验与补充E2E | [测试资料索引](fixtures/README.md) | 每个测试固定一套资料，不能混入其他目录消除冲突或补上缺口 |
| 离线Mock | F1正常／失败等、F2冲突 | 仅BM25；固定模型脚本，只证明流程 |
| 基础模块／工具检查 | R1以及部分F1/F2；[smoke](smoke/README.md) | 与业务E2E区分，不能替代真实模型决策证明 |
| 无需重新分块的运行 | [预生成块](prepared/README.md) | 必须与选定manifest匹配；改原文后重新prepare |

业务知识库最初取自F5，现独立扩充为8份制度与FAQ，包含跨文档材料要求、不同期限以及设备借用未解冲突。`fixtures` 是独立场景快照，保留原路径、元数据与正文，历史 `examples` 不重写。已有真实验收结果仅对应当时记录的资料；新版业务库的专项检查和记录放在local_validation，不冒充既有验收覆盖。

程序原始配置仍保留最小smoke入口；主README和 `.env.example` 推荐独立业务库。真实与Mock运行命令显式指定资料，避免继承错误配置。本次没有修改本机 `.env`。

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

## 维护规则

1. 扩充日常制度时修改 `knowledge_base`，同步生成对应prepared；变更引用依据后应重新验证业务效果。
2. 只有修改某个验收场景时才改其fixture，同时检查预期、重建prepared并重跑相关测试；不自动同步主知识库。
3. 资料集内部文档ID唯一，跨资料集可复用。不要将F1至F6全部合并；F6是内容替换实验，不是比F1更新的默认制度。
4. 工具故障、模型失败与执行上限由测试注入或配置，不放在知识原文。资料不足通过实际缺失信息表达，不在正文告诉模型预期状态。
5. R1保留长章节和分块关系；不能为了缩短资料把后部范围条件搬到每个片段，否则会失去读取边界的验证意义。
