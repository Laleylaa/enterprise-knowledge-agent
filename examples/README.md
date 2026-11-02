# 提交版实际材料

本目录只保留准备随项目提交的验证材料。历史全量运行、调试记录和中间复测均在 Git 忽略的 local_validation，不作为评审入口或运行依赖。

| 保留目录 | 用途 | 实际结果 |
| --- | --- | --- |
| [submission-check](submission-check/README.md) | 最近一次完整提交套件；含正常、资料不足、冲突、工具故障、真实决策路径和原始Trace | 42/42通过，0跳过；23轮真实输出、27条引用已审核 |
| [source-id-boundary](source-id-boundary/README.md) | 对完整批次发现的正文内部ID问题，修订后复跑原上下文测试 | 1/1通过，真实2轮输出未复现；修改后未全量重跑 |

这两组互相补充，不把定向复测叠加成43个独立测试，也不把旧完整成绩当作修订后全量结果。完整批次中出现内部ID的实际输出继续保留，说明发现、修改与验证过程，没有只保留成功样例。

## 评审入口

- [题目逐项对照](submission-check/requirements-checklist.md)：业务要求、六类必验与交付边界。
- [逐轮输入、实际输出、Trace](submission-check/output-review.md)：每项输出及AI辅助阅读结论。
- [真实模型决策路径](submission-check/decision-paths.md)：充分证据后结束、冲突后读取双方、读取故障后改搜索等实际路径。
- [完整批次汇总](submission-check/summary.json)、[基础与Mock JUnit](submission-check/offline-results.xml)、[真实JUnit](submission-check/real/ec1bb22981154385b7407c026e7846e1/results.xml)。
- [内部ID修订与两轮输出](source-id-boundary/README.md)：保留原始JSON、Trace和终端渲染审核结论。

## 保留范围

提交测试为题目必验6项、核心扩展12项、离线入口7项、基础检查17项；分类依据见[测试说明](../tests/README.md)。原始记录中的故障来自明确注入，后续动作由真实模型决定；Mock和本地HTTP替身不能证明真实模型决策。

重复的终端预览由保存的JSON渲染，已移至local_validation，不是额外模型运行或必需交付物。原始材料中的本机路径和时间是运行事实，请使用仓库README里的可复制命令运行。

新试跑默认写入runtime或local_validation。只有作为提交证据选定的批次才放入examples。已归档材料不会被默认测试加载，也不需要上传。
