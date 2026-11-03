# 合成资料

所有制度与 FAQ 均为合成内容。业务资料提供制度素材，测试 fixtures 按验收场景选取、裁剪或设置变体；运行时每次只加载选定资料集，不将各测试变体混为一套制度。

## 目录与用途

| 目录 | 用途 | 入口 |
| --- | --- | --- |
| `knowledge_base/` | 八份业务制度与 FAQ，作为场景设计的素材，也用于日常真实问答 | [manifest.json](knowledge_base/manifest.json) |
| `fixtures/` | 固定测试场景，明确正常、冲突、缺资料等条件 | 下方测试资料表 |
| `smoke/` | 最小接入检查，只有一句国内差旅 30 天规则 | [manifest.json](smoke/manifest.json) |
| `prepared/` | 按原文生成的检索块，供检索和读取加载 | [业务库检索块](prepared/knowledge_base.json) |

模型工具只加载 manifest 登记的制度正文，不加载 README、测试预期或运行结果。验收以 fixtures、测试输入及对应运行证据为准。

## 业务资料

文档 ID、标题、版本日期和正文路径统一在 manifest 中维护。版本日期用于标识资料版本，不自动代表生效日期或优先级。

| 文档 | 内容与关联 |
| --- | --- |
| [D01 国内差旅报销规定](knowledge_base/documents/D01.md) | 首次提交期限 30 天、提交与付款状态；凭证见 D03，补交见 D05 |
| [D02 海外差旅报销规定](knowledge_base/documents/D02.md) | 首次提交期限 15 天、外币折算与外文凭证；补交见 D05 |
| [D03 差旅报销凭证要求](knowledge_base/documents/D03.md) | 交通、住宿、电子与外文凭证，适用于 D01 和 D02 |
| [D04 请假申请规定](knowledge_base/documents/D04.md) | 申请、审批、变更与销假，不规定各假别天数 |
| [D05 报销补充材料办理规则](knowledge_base/documents/D05.md) | 通知后 5 个工作日补交、延期确认与材料复核 |
| [D06 办公设备临时借用管理办法](knowledge_base/documents/D06.md) | 总部便携投影仪、会议摄像头临时借用，归还期限 7 个自然日 |
| [D07 办公设备临时借用常见问题](knowledge_base/documents/D07.md) | 与 D06 相同范围，归还期限为 3 个自然日，保留未解冲突 |
| [D08 企业账号与权限申请指南](knowledge_base/documents/D08.md) | 账号恢复、权限审批、临时权限有效期与工单状态 |

D01 与 D02 的适用范围不同；D06 与 D07 则未提供可消解冲突的替代关系或优先级。首次提交、补交材料和权限有效期的触发条件与时间单位应分别理解。资料未提供育儿假天数、住宿金额上限或具体员工的实际审批、付款和权限状态。

## 测试资料

每个 fixture 都有独立的 `manifest.json` 与 `documents/`，对应 `prepared/<目录名>.json`。文档 ID 在资料集内部唯一，跨资料集可以复用。

| 资料入口 | 场景设计与用途 |
| --- | --- |
| [F1_single_rule](fixtures/F1_single_rule/manifest.json) | 国内 30 天及申请状态；没有凭证要求，用于明确答案、改写、上下文、部分回答及 Mock |
| [F2_conflicting_rules](fixtures/F2_conflicting_rules/manifest.json) | 同日期的 30 天与 15 天规定，无适用关系，用于冲突及通知追问 |
| [F2_newer_D02](fixtures/F2_newer_D02/manifest.json) | 仅将 D02 日期改晚，检查是否错误地按日期消解冲突 |
| [F4_scope_evidence](fixtures/F4_scope_evidence/manifest.json) | 在冲突资料中增加 D03，明确 D01 国内、D02 海外，检查跨文档查证 |
| [F5_leave_and_scope](fixtures/F5_leave_and_scope/manifest.json) | 国内、海外与请假流程；未提供育儿假天数，用于资料不足、澄清和条件更正 |
| [F6_replaced_rule](fixtures/F6_replaced_rule/manifest.json) | 将 F1 的 30 天改为 20 天，其余内容和日期不变，检查原文替换后的答案变化 |
| [R1_section_context](fixtures/R1_section_context/manifest.json) | 长章节中分开陈述期限和国内适用范围，用于读取边界及检索降级场景 |

工具失败、模型失败和执行上限通过测试注入或配置，不写入制度正文。R1 用于检查是否取得必要范围依据，不强制模型必须调用某一种工具。测试分层、预期和结果见[评估文档](../docs/03-evaluation.md)。

## 原文格式与维护

Markdown 是唯一可编辑的制度正文；manifest 使用 UTF-8 JSON，格式如下：

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

`source_path` 相对于 manifest 所在目录，只指向该目录内的 Markdown 文件。加载器保留原文空白、换行和字符位置，用于核对引用；非法元数据、越界路径或读取失败会明确报错。实现见 [document_loader.py](../src/knowledge_agent/document_loader.py)。

预生成块使用固定版本的 BGE-small-zh-v1.5 tokenizer，默认目标 320、上限 480、重叠最多 48 tokens，保存章节、字符位置和来源指纹。BM25 与读取工具加载已有块时无需 tokenizer 文件或向量权重；重新分块需要本地 tokenizer，hybrid/vector 还需要本地模型资产。

按根 README 激活环境并设置环境变量后，修改原文并重新准备对应资料，例如（macOS/Linux 与 Windows PowerShell 通用）：

```sh
python -m knowledge_agent prepare --mode real --retrieval bm25 --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json --output-dir runtime/preparation
```

首次准备资产见[根 README](../README.md#准备本地检索资产)。不要手改派生 JSON 来改变答案。业务资料与 fixtures 分别维护；修改测试资料时同步核对预期、重建检索块并运行受影响的测试，保留其输入、输出和 Trace。
