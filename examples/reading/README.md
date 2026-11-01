# 独立读取工具验证材料

代码在 [tests/reading](../../tests/reading)，组件说明见 [读取工具](../../src/knowledge_agent/reading/README.md)。本目录只记录实际工具调用：stage=standalone_read_tool、model_calls=0，没有 Agent 或模型请求。搜索定位到读取的动作由测试指定，不是模型决策记录；不能计入 P2 或 Q01～Q18 端到端成绩。

所有运行按相同 case_id/run_id 配对保存。input.json/output.json 是该次运行的最后一次调用；多步骤输入与结果完整保存在 traces 的 tool-inputs.jsonl、tool-results.jsonl，trace.jsonl 给出事件顺序，observed-evidence.json 保存已取得证据。corpus.json 保存当时原文、派生块和指纹；artifacts.json 列出分类后路径与 SHA-256。章节补读另保存实际 BM25 索引身份，故障用例另保存注入说明。

| 用例／实际范围 | 输入 | 输出 | Trace／完整调用 | 评估指标 |
|---|---|---|---|---|
| 分别读取两份冲突原文，不裁决 | [输入](inputs/conflicting_sources/aeb08ef99ee0404db5a6a03a65298f73/input.json) | [输出](outputs/conflicting_sources/aeb08ef99ee0404db5a6a03a65298f73/output.json) | [Trace](traces/conflicting_sources/aeb08ef99ee0404db5a6a03a65298f73/trace.jsonl) · [参数](traces/conflicting_sources/aeb08ef99ee0404db5a6a03a65298f73/tool-inputs.jsonl) · [返回](traces/conflicting_sources/aeb08ef99ee0404db5a6a03a65298f73/tool-results.jsonl) · [清单](traces/conflicting_sources/aeb08ef99ee0404db5a6a03a65298f73/artifacts.json) | [指标](reports/conflicting_sources/aeb08ef99ee0404db5a6a03a65298f73/reading-evaluation.json) |
| 缺失 D99：NOT_FOUND，无证据 | [输入](inputs/missing_source/570e6318c69a43abbec13897567a0839/input.json) | [输出](outputs/missing_source/570e6318c69a43abbec13897567a0839/output.json) | [Trace](traces/missing_source/570e6318c69a43abbec13897567a0839/trace.jsonl) · [参数](traces/missing_source/570e6318c69a43abbec13897567a0839/tool-inputs.jsonl) · [返回](traces/missing_source/570e6318c69a43abbec13897567a0839/tool-results.jsonl) · [清单](traces/missing_source/570e6318c69a43abbec13897567a0839/artifacts.json) | [指标](reports/missing_source/570e6318c69a43abbec13897567a0839/reading-evaluation.json) |
| 全文读取：期限和适用条件完整 | [输入](inputs/normal/d13cd1bc429c4705af674c08dc06dd5c/input.json) | [输出](outputs/normal/d13cd1bc429c4705af674c08dc06dd5c/output.json) | [Trace](traces/normal/d13cd1bc429c4705af674c08dc06dd5c/trace.jsonl) · [参数](traces/normal/d13cd1bc429c4705af674c08dc06dd5c/tool-inputs.jsonl) · [返回](traces/normal/d13cd1bc429c4705af674c08dc06dd5c/tool-results.jsonl) · [清单](traces/normal/d13cd1bc429c4705af674c08dc06dd5c/artifacts.json) | [指标](reports/normal/d13cd1bc429c4705af674c08dc06dd5c/reading-evaluation.json) |
| 章节超限后按定位读取三个块 | [输入](inputs/oversized_section/bd4eca323e934b9e831ecf74abe7636f/input.json) | [输出](outputs/oversized_section/bd4eca323e934b9e831ecf74abe7636f/output.json) | [Trace](traces/oversized_section/bd4eca323e934b9e831ecf74abe7636f/trace.jsonl) · [参数](traces/oversized_section/bd4eca323e934b9e831ecf74abe7636f/tool-inputs.jsonl) · [返回](traces/oversized_section/bd4eca323e934b9e831ecf74abe7636f/tool-results.jsonl) · [清单](traces/oversized_section/bd4eca323e934b9e831ecf74abe7636f/artifacts.json) | [指标](reports/oversized_section/bd4eca323e934b9e831ecf74abe7636f/reading-evaluation.json) |
| 重新准备后读取 20 天 | [输入](inputs/policy_after/44eb0be58d3c49919ffb055ff063a364/input.json) | [输出](outputs/policy_after/44eb0be58d3c49919ffb055ff063a364/output.json) | [Trace](traces/policy_after/44eb0be58d3c49919ffb055ff063a364/trace.jsonl) · [参数](traces/policy_after/44eb0be58d3c49919ffb055ff063a364/tool-inputs.jsonl) · [返回](traces/policy_after/44eb0be58d3c49919ffb055ff063a364/tool-results.jsonl) · [清单](traces/policy_after/44eb0be58d3c49919ffb055ff063a364/artifacts.json) | [指标](reports/policy_after/44eb0be58d3c49919ffb055ff063a364/reading-evaluation.json) |
| 替换前快照保持 30 天 | [输入](inputs/policy_before/53fc3ded1b9c4adcaab21bb02ed37d5c/input.json) | [输出](outputs/policy_before/53fc3ded1b9c4adcaab21bb02ed37d5c/output.json) | [Trace](traces/policy_before/53fc3ded1b9c4adcaab21bb02ed37d5c/trace.jsonl) · [参数](traces/policy_before/53fc3ded1b9c4adcaab21bb02ed37d5c/tool-inputs.jsonl) · [返回](traces/policy_before/53fc3ded1b9c4adcaab21bb02ed37d5c/tool-results.jsonl) · [清单](traces/policy_before/53fc3ded1b9c4adcaab21bb02ed37d5c/artifacts.json) | [指标](reports/policy_before/53fc3ded1b9c4adcaab21bb02ed37d5c/reading-evaluation.json) |
| 章节补读（初次）：从多候选中选取期限块，验证定位兼容 | [输入](inputs/section_expansion/003711d435aa46478666cf8257474a05/input.json) | [输出](outputs/section_expansion/003711d435aa46478666cf8257474a05/output.json) | [Trace](traces/section_expansion/003711d435aa46478666cf8257474a05/trace.jsonl) · [参数](traces/section_expansion/003711d435aa46478666cf8257474a05/tool-inputs.jsonl) · [返回](traces/section_expansion/003711d435aa46478666cf8257474a05/tool-results.jsonl) · [清单](traces/section_expansion/003711d435aa46478666cf8257474a05/artifacts.json) | [指标](reports/section_expansion/003711d435aa46478666cf8257474a05/reading-evaluation.json) |
| 章节补读（收紧后）：首次只返回期限块，读取章节取得范围 | [输入](inputs/section_expansion/224d4882967d4c37af6d5cf4c65f8bbf/input.json) | [输出](outputs/section_expansion/224d4882967d4c37af6d5cf4c65f8bbf/output.json) | [Trace](traces/section_expansion/224d4882967d4c37af6d5cf4c65f8bbf/trace.jsonl) · [参数](traces/section_expansion/224d4882967d4c37af6d5cf4c65f8bbf/tool-inputs.jsonl) · [返回](traces/section_expansion/224d4882967d4c37af6d5cf4c65f8bbf/tool-results.jsonl) · [清单](traces/section_expansion/224d4882967d4c37af6d5cf4c65f8bbf/artifacts.json) | [指标](reports/section_expansion/224d4882967d4c37af6d5cf4c65f8bbf/reading-evaluation.json) |
| 注入读取故障：READ_FAILED，无重试／证据 | [输入](inputs/tool_failure/84ab5060c756413d820229d64e07061b/input.json) | [输出](outputs/tool_failure/84ab5060c756413d820229d64e07061b/output.json) | [Trace](traces/tool_failure/84ab5060c756413d820229d64e07061b/trace.jsonl) · [参数](traces/tool_failure/84ab5060c756413d820229d64e07061b/tool-inputs.jsonl) · [返回](traces/tool_failure/84ab5060c756413d820229d64e07061b/tool-results.jsonl) · [清单](traces/tool_failure/84ab5060c756413d820229d64e07061b/artifacts.json) | [指标](reports/tool_failure/84ab5060c756413d820229d64e07061b/reading-evaluation.json) |

## 实际测试报告

- [冒烟](reports/smoke/read-tool-results.xml)：3 passed。
- [契约](reports/contract/read-tool-results.xml)：23 passed。
- [业务](reports/business/read-tool-results.xml)：7 passed；七个用例产生八组运行，资料替换包含前后两组。
- [边界](reports/boundary/read-tool-results.xml)：14 passed。
- [补读前提收紧后的复测](reports/business/section-expansion-refined-results.xml)：1 passed，为上述七个业务用例之一的复测，不另增加用例数；新旧记录均保留。
- [原检索回归](../retrieval/reports/read-tool-compatibility-results.xml)：47 passed。

读取共 47 个测试，无跳过；检索另 47 个测试。未运行 Agent 测试、未连接模型 API。超大章节与资料替换等依赖本机缓存的固定 tokenizer，其他机器缺失时会明确跳过，基础读取使用提交的预生成块。

```sh
python -m pytest tests/reading -q --junitxml=examples/reading/reports/current-results.xml --examples-dir=examples
```

不带 --examples-dir 时只使用测试临时目录；该参数只归档登记的实际运行，不启用模型。完整结果、收紧补读前提的原因及已知限制见 [评估文档](../../docs/03-evaluation.md)。
