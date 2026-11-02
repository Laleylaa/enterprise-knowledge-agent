# 日常业务知识库

这是主 README 推荐的真实问答入口。全部内容是为本项目编写的合成员工制度与 FAQ，不代表任何真实企业的政策。运行时通过 `--corpus`、`--prepared` 或环境变量显式选择本资料集。

## 文档与范围

| 文档 | 版本日期 | 内容与关联 |
| --- | --- | --- |
| [D01 国内差旅报销规定](documents/D01.md) | 2026-11-02 | 国内首次提交30天、提交与付款状态；凭证见D03，补交见D05 |
| [D02 海外差旅报销规定](documents/D02.md) | 2026-11-02 | 海外首次提交15天、外币折算方法、外文凭证关联；补交见D05 |
| [D03 差旅报销凭证要求](documents/D03.md) | 2026-11-02 | 交通、住宿、电子与外文凭证；适用于D01、D02 |
| [D04 请假申请规定](documents/D04.md) | 2026-11-02 | 提前申请、突发情况、审批、变更与销假；不规定各假别天数 |
| [D05 报销补充材料办理规则](documents/D05.md) | 2026-11-02 | 通知后5个工作日补交、延期确认、材料复核；与首次提交期限区分 |
| [D06 办公设备临时借用管理办法](documents/D06.md) | 2026-10-01 | 总部便携投影仪、会议摄像头临时借用；归还期限7个自然日 |
| [D07 办公设备临时借用常见问题](documents/D07.md) | 2026-10-01 | 与D06相同对象的申请与归还FAQ；归还期限3个自然日 |
| [D08 企业账号与权限申请指南](documents/D08.md) | 2026-11-02 | 账号恢复、权限审批、临时权限15个自然日有效期及工单状态 |

入口为 [manifest.json](manifest.json)，检索块为 [knowledge_base.json](../prepared/knowledge_base.json)。文档ID、标题与版本日期在manifest维护。版本日期是资料版本标记，不自动代表生效日期或制度优先级。

## 文档关系与保留缺口

- D01与D02的国内/海外范围不同，期限不同不构成同场景冲突。未明确出差范围时，应结合历史或补充用户条件。
- D01、D02分别引用D03与D05，支持期限与材料的跨文档回答。首次提交、补交材料和临时权限有效期的触发条件与时间单位不同，不能互相套用。
- D06与D07对相同设备和人员范围规定了不同归还期限，未提供替代关系或优先级。两份原文均保留，便于展示冲突查证。不能仅凭“管理办法”与“FAQ”的名称自行决定优先级；本说明不作为工具可检索的制度依据。
- 育儿假等假别的具体天数、住宿报销金额上限、某日期实际外汇汇率、具体员工的审批/付款/权限状态未提供。不得从办理流程推导这些事实。

模型工具仅加载manifest中登记的8份原文，不加载本README、测试预期或运行结果。正文只陈述合成业务事实，没有预设工具动作或任务状态。

## 可探索的问题

- 国内差旅结束后多久提交报销，住宿需要哪些凭证？
- 海外差旅首次提交报销与收到财务补充材料通知后的期限各是多久？
- 海外住宿凭证是外文，还要补什么材料？
- 提交了补材料延期申请，是不是就可以晚交？
- 总部临时借用便携投影仪，领用后几天归还？
- 请假申请已经提交，是否代表请假生效？
- 报销系统临时权限到期了，续期申请正在处理中，还能继续使用吗？
- 公司育儿假有多少天？

这些问题说明资料用途，不等于全部已通过真实测试。此次扩充的专项验证放在本地 `local_validation/tests/knowledge_base/`，运行记录在 `local_validation/examples/knowledge_base_refresh/`；原提交版测试与examples未新增用例或记录。原有fixture验收结果不能直接视为新版业务库的验收结果。

## 维护与准备

本库最初取自F5的三份资料，现已独立扩充为8份。现有fixtures、smoke及其派生块保持原样；不得把它们的受控变体直接拼入本库。原文变化后重新生成派生块及本地向量缓存：

```sh
PYTHONPATH=src python -m knowledge_agent prepare --retrieval hybrid \
  --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json \
  --output-dir runtime/preparation/knowledge-base

PYTHONPATH=src python -m knowledge_agent chat --mode real --retrieval hybrid \
  --corpus data/knowledge_base/manifest.json --prepared data/prepared/knowledge_base.json \
  --question "总部临时借用便携投影仪，领用后几天归还？" --format json \
  --output-dir runtime/chat
```

首次下载模型资产需按主README显式添加 `--download`；prepare不调用主模型。只需离线分块时可选 `--retrieval bm25`，仍需本地tokenizer。
