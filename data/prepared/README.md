# 预生成检索块

这些JSON由正式prepare流程生成，属于派生资料；唯一原文是各资料目录的Markdown及manifest。不要手工修改JSON来改变答案。

| 文件 | 对应原文 | 块数 |
| --- | --- | --- |
| [knowledge_base.json](knowledge_base.json) | [日常业务库](../knowledge_base/manifest.json) | 10 |
| [F1_single_rule.json](F1_single_rule.json) | [F1](../fixtures/F1_single_rule/manifest.json) | 4 |
| [F2_conflicting_rules.json](F2_conflicting_rules.json) | [F2](../fixtures/F2_conflicting_rules/manifest.json) | 4 |
| [F2_newer_D02.json](F2_newer_D02.json) | [F2日期变体](../fixtures/F2_newer_D02/manifest.json) | 4 |
| [F3_explicit_scope.json](F3_explicit_scope.json) | [F3](../fixtures/F3_explicit_scope/manifest.json) | 8 |
| [F4_scope_evidence.json](F4_scope_evidence.json) | [F4](../fixtures/F4_scope_evidence/manifest.json) | 6 |
| [F5_leave_and_scope.json](F5_leave_and_scope.json) | [F5](../fixtures/F5_leave_and_scope/manifest.json) | 10 |
| [F6_replaced_rule.json](F6_replaced_rule.json) | [F6](../fixtures/F6_replaced_rule/manifest.json) | 4 |
| [R1_section_context.json](R1_section_context.json) | [R1](../fixtures/R1_section_context/manifest.json) | 5 |

全部使用BAAI/bge-small-zh-v1.5 tokenizer，revision `7999e1d3359715c523056ef9478215996d62a620`，tokenizer.json SHA-256 `48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26`。块目标320、上限480、重叠最多48 tokens。JSON保存原文、章节、字符位置及来源指纹。

依赖安装后，BM25和读取工具加载这些块不需要tokenizer文件、向量权重或网络。重新分块需要本地固定版本tokenizer；完整hybrid还需要本地向量模型资产，预生成块不包含向量权重。资料或分块配置更改后必须重新prepare，启动时会校验匹配关系。

```sh
# 已有本地tokenizer时重建业务库分块；不调用主模型，不下载资产
PYTHONPATH=src python -m knowledge_agent prepare --retrieval bm25 \
  --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json
# 测试资料同理，显式成对指定路径
PYTHONPATH=src python -m knowledge_agent prepare --retrieval bm25 \
  --corpus data/fixtures/F1_single_rule/manifest.json --prepared data/prepared/F1_single_rule.json
```

首次需要下载时，使用主README的 `prepare --retrieval hybrid --download`。本次仅新建业务库的派生块，原测试资料块不重建、不覆盖。
