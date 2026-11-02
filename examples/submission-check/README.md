# 提交版完整重跑与审核（2026-11-02）

后续修订：明确回答字段的内部ID边界后，原上下文测试定向1/1通过，两轮输出均未复现，见[后续报告](../source-id-boundary/README.md)。下文保留修订前的完整批次与问题证据。

**42项全部通过，0失败、0错误、0跳过。** 真实模型23轮输出、27条引用已逐条阅读，本批六类题目必验业务符合预期。但上下文首轮的回答正文出现内部source_id，未完全满足用户新增的“内部信息仅留JSON和Trace”展示要求；最终提交信息与个人记录也尚未完成。因此不宣称整个交付已完成。

本次未新增/修改测试，未修改产品代码或资料，未对失败反复抽样。代码、测试、数据及配置134份文件运行前后哈希一致。此前失败与历史批次继续保留。

## 自动测试结果

| 分层 | 本次结果 | 证据 |
| --- | --- | --- |
| 基础模块、工具、连接 | 17/17通过 | [基础与Mock JUnit](offline-results.xml) |
| 离线Mock | 7/7通过 | [24项运行事实](offline-facts.json)；[原始材料](offline/) |
| 六类必验真实业务 | 6/6通过 | [真实JUnit](real/ec1bb22981154385b7407c026e7846e1/results.xml) |
| 补充真实业务 | 12/12通过 | [真实汇总](real/ec1bb22981154385b7407c026e7846e1/summary.json)；[完整运行日志](real/ec1bb22981154385b7407c026e7846e1/pytest.log) |

[合并汇总](summary.json) · [题目逐项对照](requirements-checklist.md) · [23轮输入/输出/Trace与阅读结论](output-review.md) · [真实动态路径](decision-paths.md) · [独立阅读记录](semantic-review.json) · [代码及资料快照](code-data-before.json) · [提交范围与归档完整性](scope-check.json)

## 实际发现：正文包含内部证据ID

输入：`国内差旅报销有什么要求？`

输出第二段中出现：`3c428cbd87584320a61313b6f01c67bc:E4:S0说明“已提交”表示申请已进入处理队列……`

该ID已经写在回答模型提交的正文中，当前终端会原样展示。制度内容有真实原文支持，问题属于展示边界，而非错误引用或编造制度。现有自动测试没有检查自然语言正文是否包含内部定位ID，因此该用例自动通过。本次保留发现，没有修改输出或代码掩盖它。

[原始输出](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/required_context/3c428cbd87584320a61313b6f01c67bc/output.json)

旧问题“未完成却显示中断原因completed”的独立诊断行经渲染核对已不再出现，故障回复见[原始输出](real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/required_tool_failure/9a6f8e550b4b4b298b46b3cbe9d56f90/output.json)。渲染预览仅在local_validation归档，不是新增模型运行或新测试。

## 业务阅读结论与边界

- 明确答案、冲突查证、资料外问题、改写、上下文追问、工具失败均符合本批场景预期；资料替换后回答由30天变为20天。
- 持续故障由模型正常结束取证并提交incomplete；读取失败后改用搜索、单分支降级但充分证据仍回答等路径有实际记录。
- 澄清问句重复、附带原文状态说明、额外引用标题属于非阻断表达备注，不计为题目业务失败。通知口头措辞沿用用户已确认的接受口径，不重新判错。
- 阅读故障用例的decision_summary称“直接读取到”原文，工具实际先读取失败再搜索成功；以完整Trace为准。未将此表述当作读取工具成功的证据。
- 本批业务测试使用固定fixtures，不代表8份knowledge_base所有问答已验收；没有重跑本地探索测试。
- 测试运行于已有依赖环境，不是一次全新机器安装验证。语义审核为AI辅助阅读，不等同本人独立验收或长期稳定性证明。

## 提交待办

正文内部ID问题已在后续定向修订中补充约束并复测，见页首链接。本人与提交待办：填写正式题号、实际投入时长，核实个人贡献与复盘；完成最终提交与推送，填写最终commit SHA及GitHub URL，确认评审可访问。本测试批次未联网核验远程权限。

## 复现命令

```sh
.venv/bin/python -m pytest tests/contracts tests/e2e/offline -q --examples-dir examples/submission-check/offline --junitxml=examples/submission-check/offline-results.xml --evaluation-facts=examples/submission-check/offline-facts.json
.venv/bin/python -m knowledge_agent evaluate --mode real --run-live --output-dir examples/submission-check/real
```

复跑时请使用新的输出目录保留本批材料；首次准备依赖、密钥与本地模型资产参见仓库README。
