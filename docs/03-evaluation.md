# 测试与评估

本报告评估当前提交版本，验收依据为[需求文档](01-requirements.md)，取证与回复职责以[技术方案](02-solution.md)为准。测试代码位于 `tests/`，输入、实际输出、Trace及测试结果位于 `examples/submission-check/`，评审不依赖本地开发记录。

## 1. 测试范围与结果

完整测试共 **49项，49项通过，0失败、0错误、0跳过**。测试项包含参数化场景，不等于测试文件数。结果见[测试汇总](../examples/submission-check/summary.json)和[逐项结果](../examples/submission-check/results.xml)。

| 测试类别 | 测试入口 | 验证范围 | 实际结果 |
| --- | --- | --- | --- |
| 真实业务必验 | [required](../tests/e2e/required/test_acceptance.py) | 明确答案、文档冲突、资料外问题、相似改写、上下文追问、工具失败 | 6/6通过 |
| 真实业务扩展 | [业务边界](../tests/e2e/extended/test_business_edges.py)、[检索降级](../tests/e2e/extended/test_hybrid_partial.py) | 适用关系、冲突追问、资料替换、部分回答、澄清、条件更正、故障恢复及停止条件 | 12/12通过 |
| 离线Mock | [offline](../tests/e2e/offline/test_mock.py) | 正常、冲突、缺资料、工具失败、恢复、预算停止及不支持的输入 | 7/7通过 |
| 基础契约 | [contracts](../tests/contracts/) | 配置入口、SDK连接、工具协议、执行预算、引用、会话证据及材料导出 | 24/24通过 |

测试按业务验收与基础契约分层；`tests/support/` 提供共用运行和证据检查，不存放独立用例，也不依赖本地开发归档。扩展场景围绕制度适用、冲突、条件更正、部分回答与故障恢复组织，具体资料用途见[测试资料](../data/README.md#测试资料)。

真实业务使用 `deepseek-flash`、hybrid检索及独立合成资料fixtures，通过产品CLI执行。故障场景由测试注入工具错误，模型依据实际反馈决定后续动作。离线Mock实际执行BM25和原文读取，使用预设模型响应，只验证流程；基础契约使用本地受控模型或HTTP替身，不调用真实模型服务。

完整批次保留41组运行记录，其中包含23轮真实回答、28条真实回答引用。[全部输入、输出与Trace](../examples/submission-check/cases.md)按用例索引，共用资料快照包含文档ID、版本日期及原文。

另对文档冲突、较新版本冲突、通知追问和明确适用范围4个既有用例，各固定执行3次，**12次全部通过**。这些重复执行单独计数，不累加到49项中；包含15轮真实回答、30条引用，见[定向复测材料](../examples/README.md#批次与索引)及[逐次结果](../examples/submission-check/repeat-check/results.xml)。

## 2. 业务验收预期与实际结果

### 2.1 题目必验场景

| 场景与输入 | 测试预期 | 当前版本实际结果 | 运行证据 |
| --- | --- | --- | --- |
| 明确答案：国内差旅报销期限多久；D01规定30天 | 回答期限与起算条件，引用D01，resolved | 回答行程结束后30天内提交，引用D01，resolved | [输出](../examples/submission-check/cases/required_clear_answer/5cc686b8d37c4a6f9991272cb3663f67/output.json) · [Trace](../examples/submission-check/cases/required_clear_answer/5cc686b8d37c4a6f9991272cb3663f67/trace.jsonl) |
| 文档冲突：询问期限；D01为30天、D02为15天，无适用关系 | 观察冲突后继续查证，取证为conflict；回复列出双方引用并追问，不擅自选择期限 | 读取双方原文后仍为conflict；回复保留30天与15天，needs_info | [输出](../examples/submission-check/cases/required_conflict/692b1655cf8f40a691b29e35ec4e8eb9/output.json) · [Trace](../examples/submission-check/cases/required_conflict/692b1655cf8f40a691b29e35ec4e8eb9/trace.jsonl) |
| 资料外问题：公司育儿假有多少天；资料未提供天数 | 正常查证后说明资料缺口，unresolved，不编造天数 | 说明未取得育儿假天数原文，unresolved，无引用 | [输出](../examples/submission-check/cases/required_missing/6056a742c6c244428310b12857a693bc/output.json) · [Trace](../examples/submission-check/cases/required_missing/6056a742c6c244428310b12857a693bc/trace.jsonl) |
| 相似改写：“国内差旅报销期限多久？”与“国内出差回来最迟多久交报销？” | 两种问法的结论、适用条件与起算点一致，均有有效引用 | 均依据D01回答国内差旅行程结束后30天内提交，resolved | [原问输出](../examples/submission-check/cases/required_paraphrase_a/800496d5be08461fbb79d4fe266059e2/output.json) · [改写输出](../examples/submission-check/cases/required_paraphrase_b/d03d57ab4b3e417a879236c22938bc1e/output.json) |
| 上下文追问：先问国内差旅报销要求，再问“期限呢” | 承接指代，依据有效原文回答；已核验原文可复用 | 第二轮零工具调用，复用D01原文回答30天，resolved | [追问输出](../examples/submission-check/cases/required_context/2f2b61c33fe64133a5e5d5e8837ca32d/output.json) · [追问Trace](../examples/submission-check/cases/required_context/2f2b61c33fe64133a5e5d5e8837ca32d/trace.jsonl) |
| 工具失败：询问国内差旅期限，检索持续报错，模型仍可用 | 说明查证受阻，incomplete，不伪造期限或引用 | 连续检索失败后由回复模块说明未取得原文，incomplete，无引用 | [输出](../examples/submission-check/cases/required_tool_failure/feb40b5fce2b4288829f215c782262ac/output.json) · [Trace](../examples/submission-check/cases/required_tool_failure/feb40b5fce2b4288829f215c782262ac/trace.jsonl) |

各场景的原始输入、对应资料及完整运行记录均可从[材料索引](../examples/submission-check/cases.md)定位。工具失败时按预期返回incomplete、资料不足时按预期返回unresolved，均属于对应测试通过。

### 2.2 补充业务场景

| 场景 | 测试预期 | 当前版本实际结果 |
| --- | --- | --- |
| 较新版本的冲突制度 | 日期新旧不能单独消解冲突；继续查证并标记conflict | 保留双方引用，conflict；回复needs_info，未选择较新制度 |
| 明确适用范围 | 查证D03说明的适用关系，再依据适用条款回答 | D03明确D01适用于国内差旅；取证sufficient，回复30天、resolved |
| 冲突后的通知转述 | 转述不能替代制度原文；用户已无线索时不重复追问 | 两轮取证均为conflict；回复由needs_info变为unresolved，仍保留双方引用 |
| 问题对象不明 | 不猜测对象，不调用工具，追问必要信息 | 零工具调用、无引用，needs_info |
| 部分诉求缺资料 | 保留有据部分，列出未回答事项，不标为resolved | 回答30天期限，列出凭证要求的资料缺口，unresolved |
| 资料替换并导入旧历史 | 30天改为20天后重新取证，答案与引用采用新原文 | 前后均检索，答案由30天变为20天，未引用旧期限 |
| 明确询问申请状态 | 根据状态定义回答，不只返回期限条款 | 引用“已提交不代表审核通过”，resolved |
| 用户更正国内为海外 | 以新条件匹配规则 | 答案由D01的30天变为D02的15天 |
| 首次工具失败后恢复 | 根据错误反馈继续必要查证，取得依据后回答 | 后续调用取得有效原文，回答30天、resolved |
| 原文读取持续失败 | 已有检索原文仍可作为依据；根据故障调整取证方式 | 读取失败后限定D01检索，依据提交期限原文回答30天 |
| 向量分支失败，BM25证据充分 | 保留有效分支原文，不因降级直接判定未完成 | 依据BM25取得的原文回答30天、resolved |
| 仅问30天规则是否适用于海外差旅 | 观察到明确排除海外的原文后停止，不查未询问的替代期限 | 一次检索后结束，回答不适用、resolved、空缺口，无后续业务工具调用或回答阶段补查 |

补充场景对应[扩展业务测试](../tests/e2e/extended/test_business_edges.py)与[hybrid降级测试](../tests/e2e/extended/test_hybrid_partial.py)，输入、输出和Trace见[运行记录](../examples/submission-check/cases.md)。其中[资料替换后的Trace](../examples/submission-check/cases/Q18b_after/e0300a30a3b040f3b044c4e90b2e3673/trace.jsonl)展示重新查证，[适用性Trace](../examples/submission-check/cases/hybrid_partial_section_context/8586030ce1ab46a7acb26bcdf74b0855/trace.jsonl)展示取得充分依据后停止。

## 3. 两阶段状态与动态决策验证

冲突与适用关系用例分别断言取证原因及最终任务状态。取证的conflict表示原文冲突仍未消解；回复是否需要追问，由原文和用户条件决定。本批运行记录中的实际组合如下：

| 条件 | 取证原因 | 最终任务状态 | 证据 |
| --- | --- | --- | --- |
| 两份规定冲突，仍需确认适用制度 | conflict | needs_info | [冲突Trace](../examples/submission-check/cases/required_conflict/692b1655cf8f40a691b29e35ec4e8eb9/trace.jsonl) |
| 冲突未解，用户已明确没有更多可核实线索 | conflict | unresolved | [通知追问Trace](../examples/submission-check/cases/extended_notification/f40ecdc57a754a75a7f29e4b8ea59bd6/trace.jsonl) |
| 原文明示适用范围，期限有据 | sufficient | resolved | [范围确认Trace](../examples/submission-check/cases/extended_scope/41afd461eb9e446bac0657c858a6ad57/trace.jsonl) |
| 正常查证后仍缺所问制度内容 | missing | unresolved | [资料不足Trace](../examples/submission-check/cases/required_missing/6056a742c6c244428310b12857a693bc/trace.jsonl) |
| 必要检索持续失败且没有有效原文 | blocked | incomplete | [工具失败Trace](../examples/submission-check/cases/required_tool_failure/feb40b5fce2b4288829f215c782262ac/trace.jsonl) |

动态决策的实测路径包括：

- [检索充分后结束](../examples/submission-check/cases/required_clear_answer/5cc686b8d37c4a6f9991272cb3663f67/trace.jsonl)：检索返回期限原文，模型观察后结束取证。
- [发现冲突后继续读取](../examples/submission-check/cases/required_conflict/692b1655cf8f40a691b29e35ec4e8eb9/trace.jsonl)：检索返回30天和15天，模型读取双方查证，仍无适用依据时以conflict结束。
- [读取失败后改用检索](../examples/submission-check/cases/extended_read_failure/bfc9444d613c4e3ca2626af87d7babba/trace.jsonl)：模型观察读取错误，改为限定D01检索，取得有效原文后结束。

Trace保留实际模型动作、工具参数、返回摘要、后续动作与简短依据；这些真实路径用于核对模型是否响应工具结果。

## 4. 基础验证与结果核对

基础契约24项覆盖：配置与入口5项、hybrid分支结果2项、执行预算2项、SDK工具连接1项、HTTP超时与认证失败2项、读取与引用4项、块扩展章节1项、会话证据5项、提交材料导出2项。

其中，会话证据测试检查原文复用、资料变化失效、清空会话、历史导入和无效证据拒绝；历史导入场景验证无有效原文的sufficient被拒绝，模型收到反馈后重新取证。预算与请求失败测试验证停止后续调用并返回incomplete；材料导出测试验证输出保真、来源关联和失败统计。这些测试只证明对应的本地协议与执行行为。

自动检查覆盖状态字段、取证原因、实际工具执行、证据送达、引用来源与连续原文片段。完整批次的 23 轮真实回答及 28 条引用，另经 AI 辅助阅读核对结论、适用条件和原文支持关系；根据现有测试未发现无依据期限或擅自消解冲突。在已核对的回答正文、资料缺口及追问中，未发现内部证据标识外露。定向复测的 15 轮真实回答及 30 条引用采用同样的核对方式。

安装与凭证配置见[README](../README.md)，完整测试及材料生成命令见[提交材料说明](../examples/README.md#完整复跑与打包)，固定轮次验证命令见[定向复测步骤](../examples/README.md#定向复测)。默认运行pytest会跳过18项真实模型测试；真实业务须显式启用 `--run-live`。

## 5. 当前问题与验证限制

本批自动测试无失败项。当前限制主要有两点：

- 测试基于预置合成资料和固定用例，验证结论限于本次覆盖的场景。
- 个别回复仍有多余背景或不够精确的措辞，表达可进一步精简，见[答复示例](../examples/submission-check/cases/extended_notification/f40ecdc57a754a75a7f29e4b8ea59bd6/output.json)。
