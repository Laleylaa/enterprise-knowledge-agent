# 回答正文内部ID边界修订（2026-11-02）

原回答提示词只说明使用source_id选择原文、不要编造ID，没有明确禁止把有效ID抄入正文；DraftPart.text也未说明这一边界。本次明确内部来源ID只用于source_ids数组，正文、缺口、追问不得出现或沿用内部ID；引用序号由程序生成，D01等公开文档ID仍可用于区分制度。同步补充模型实际接收的字段描述。

仅修改提示词和字段说明，没有增加运行时替换、过滤或状态改写，没有新增或修改测试。

## 本次验证

仅执行现有 `tests/e2e/required/test_acceptance.py::test_context_followup` 一次，**1/1通过，真实2轮输出**。逐条阅读并核对交接包中的内部ID：两轮正文、缺口、追问及实际终端渲染均未出现内部定位ID；引用保留D01和原文，首轮回答有据，“期限呢”正确承接并回答行程结束后30天内提交。

- [自动汇总](cf4156e06e9840dd891440615f4d5ec6/summary.json)、[JUnit](cf4156e06e9840dd891440615f4d5ec6/results.xml)、[阅读与核对记录](review.json)。
- 首轮：[实际输出](cf4156e06e9840dd891440615f4d5ec6/artifacts/e2e/outputs/required_context/a45d1bc372ab41f5b48ab4d32cf041c1/output.json)、[Trace](cf4156e06e9840dd891440615f4d5ec6/artifacts/e2e/traces/required_context/a45d1bc372ab41f5b48ab4d32cf041c1/trace.jsonl)。
- 追问：[实际输出](cf4156e06e9840dd891440615f4d5ec6/artifacts/e2e/outputs/required_context/7d2e990916f44a95a3373081cae590de/output.json)、[Trace](cf4156e06e9840dd891440615f4d5ec6/artifacts/e2e/traces/required_context/7d2e990916f44a95a3373081cae590de/trace.jsonl)。

终端展示已用本批实际JSON渲染核对，没有修改模型文字；重复的预览文本仅在local_validation归档。原来出现ID的[失败输出](../submission-check/real/ec1bb22981154385b7407c026e7846e1/artifacts/e2e/outputs/required_context/3c428cbd87584320a61313b6f01c67bc/output.json)仍保留。本次结果支持“边界已明确、定向复测未复现”，不证明长期稳定，也不将此前42/42当作修改后全量结果。

```sh
.venv/bin/python -m knowledge_agent evaluate --mode real --run-live --suite tests/e2e/required/test_acceptance.py::test_context_followup --output-dir examples/source-id-boundary
```
