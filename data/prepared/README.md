# 离线原文块

F1、F2 的 JSON 均由 `knowledge_agent.retrieval prepare` 实际生成，是派生缓存，不是可编辑知识原文。唯一正文源仍为各资料集的 Markdown＋manifest。

- tokenizer：BAAI/bge-small-zh-v1.5，revision `7999e1d3359715c523056ef9478215996d62a620`。
- tokenizer.json SHA-256：`48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26`。
- tokenizers 0.22.1；块目标 320、上限 480、重叠最多 48 tokens。
- 两套资料各有 4 个块，包含实际字符位置、标题位置、原文、索引文本、token 数和版本指纹。

首次下载 tokenizer 的文件保存在 runtime，不随代码提交。依赖已安装时，使用这些块进行搜索不需要 tokenizer 文件、模型权重、密钥或网络。重分块需要本地 tokenizer；代码不会自动下载或改用字符长度代替。

每次启动核对来源和配置指纹、块校验和、章节／原文位置及覆盖范围；资料或分块配置更改后必须重建。BM25 参数改变只重建排名索引，其索引指纹也随之变化。

```sh
PYTHONPATH=src python -m knowledge_agent.retrieval download-tokenizer
PYTHONPATH=src python -m knowledge_agent.retrieval prepare --corpus data/fixtures/F1_single_rule/manifest.json --prepared data/prepared/F1_single_rule.json
PYTHONPATH=src python -m knowledge_agent.retrieval prepare --corpus data/fixtures/F2_conflicting_rules/manifest.json --prepared data/prepared/F2_conflicting_rules.json
```
