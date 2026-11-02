# 提交版实际材料

**当前完整结果：真实hybrid 18项自动通过（23轮），Mock BM25 7项通过，基础契约17项通过。** 真实通知追问仍有1轮语义缺陷，自动通过不等于整体语义验收通过。

- [真实批次汇总](real/84abfb9714094e4587361ecc85a2a163/summary.json)、[JUnit](real/84abfb9714094e4587361ecc85a2a163/results.xml)、[逐轮语义核对](real/84abfb9714094e4587361ecc85a2a163/semantic-review.json)、[逐轮文件索引](real/84abfb9714094e4587361ecc85a2a163/review-index.md)。
- [Mock批次汇总](mock/bf38e07c4e6b491a98241e9ea2a5713a/summary.json)、[Mock JUnit](mock/bf38e07c4e6b491a98241e9ea2a5713a/results.xml)：6个固定场景有运行记录，1个不支持输入检查明确拒绝且不生成伪造运行。
- [基础契约JUnit](contracts/results.xml)、[独立副本验证](contracts/isolated-check.json)、[独立副本JUnit](contracts/isolated-results.xml)。独立副本不含local_validation、runtime、模型权重或.env，复用已安装依赖。
- [历史失败说明](history/response-wording/README.md)：保留修订前的两项真实口径问题，非当前批次。

## 业务映射

每个链接进入实际输出；同case_id/run_id的输入、工具参数/返回及Trace见逐轮索引。没有用理想答案替代实际输出。

| 分层 | 验收点 | 预期 | 实际输出 |
| --- | --- | --- | --- |
| 必验 | 明确答案 | resolved，期限、范围和起算条件有原文引用 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_clear_answer/d27324d1dc574e619e7d226388810ba5/output.json) |
| 必验 | 文档冲突 | 观察双方后查证，保留30/15天冲突并追问 | [needs_info](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_conflict/37277fc358e944d8b21a4b091f12c7ba/output.json) |
| 必验 | 资料外问题 | 查证后unresolved，不编造育儿假天数 | [unresolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_missing/9e4305261c134c9fbe37beb3f515297e/output.json) |
| 必验 | 改写问题：原问 | 原问与改写结论相同且引用一致 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_paraphrase_a/931b47c05d4a4da088890c2165bb1176/output.json) |
| 必验 | 改写问题：改写 | 原问与改写结论相同且引用一致 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_paraphrase_b/69f6cc694bfe4a34b9ecbab0cd057970/output.json) |
| 必验 | 上下文追问 | 真实前一轮历史；第二轮理解期限所指并重新取证 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_context/41f00d345cd24088a0312e7ca4b54753/output.json) / [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_context/afbb99b5722545b3b4669523ab104756/output.json) |
| 必验 | 工具失败 | 实际注入失败，incomplete，无伪造引用 | [incomplete](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/required_tool_failure/29919e3677a046449fb0bd834da40f39/output.json) |
| 补充 | 新版本日期不自动消解冲突 | 查证适用关系，不按日期选15天 | [needs_info](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_conflict_newer/7f6be3a9f2884c3b9172d6200e2ef837/output.json) |
| 补充 | 对象不明 | needs_info，不猜测所指事项 | [needs_info](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_unknown_referent/39cf800766614180903a5e231df0af80/output.json) |
| 补充 | 部分可答 | 期限引用有据，凭证缺口保留 | [unresolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_partial_answer/36189100861245c580d1c7dc8c0e85cb/output.json) |
| 补充 | 资料替换：替换前 | 30天实际原文 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/Q18b_before/d98fd8297fd0457ea697003cbd9d5894/output.json) |
| 补充 | 资料替换：带旧历史重问 | 更换真实源快照，答案与引用变20天 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/Q18b_after/034d48ea22634a1c9219fc4227f4d083/output.json) |
| 补充 | 读取失败但搜索取得依据 | 如实披露读取失败，保留搜索原文 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_read_failure/b82f9bfc169d4fcab3db8bd5e7be9d2a/output.json) |
| 补充 | 适用范围查证 | D03确认适用D01，引用范围和国内期限 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_scope/d3a882a0dfc242afa39f12e9fb23251f/output.json) |
| 补充 | 通知忠实转述 | 不擅自采用用户转述期限；通知形式不推断 | [needs_info](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_notification/9aba9708e23e45e98c1c70cc18f8a92b/output.json) / [unresolved（语义缺陷）](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_notification/231fc6f8163645fab41a7592885b9746/output.json) |
| 补充 | 明确问申请状态 | 引用状态定义回答，不被期限示例带偏 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_status/3733a0003580466da221e13b51341e97/output.json) |
| 补充 | 暂时工具失败后恢复 | 模型观察错误后再次选择工具并成功取得证据 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_recovery/2a2de31ace564c4985fde230ec981f4a/output.json) |
| 补充 | 用户更正适用条件 | 国内30天→海外15天，按最新条件取证 | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_scope_correction/a42fe3fdda214d2887c243df669b05ee/output.json) / [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/extended_scope_correction/335b31468cec4d26aec471a65ec94c17/output.json) |
| 补充 | 向量超时但BM25充分 | 一次搜索后直接resolved | [resolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/hybrid_partial_sufficient/db2ac0181b7f4afc9370d071385c5616/output.json) |
| 补充 | 向量超时且首次片段缺范围 | 取得范围条款，不把国内30天套用海外 | [unresolved](real/84abfb9714094e4587361ecc85a2a163/artifacts/e2e/outputs/hybrid_partial_section_context/859fc5bf5f8347b38f2e24c93d680452/output.json) |

## 决策路径与证据边界

[实际路径摘要](real/84abfb9714094e4587361ecc85a2a163/decision-paths.md)展示步骤、工具参数、返回摘要及下一步依据。至少两条真实模型路径：证据充分搜索后直接回答；发现冲突后读取双方再追问。另包含资料不足补查、读取失败后转搜索、首个检索失败后由模型再次选择搜索。恢复不是程序自动重试。

hybrid超时是显式测试注入，BM25和主模型实际运行；该范围用例实际通过搜索取得限定条款，不能宣称模型必然调用章节读取。章节扩展能力在基础工具检查中独立验证。

执行上限由正式Mock budget端到端和基础预算检查验证：超过预算返回incomplete及明确termination_reason。Mock循环不计真实模型决策证据。

原始JSON中存在本机路径和原运行时间，它们是运行事实，不作为他人电脑上的运行命令。请使用README中的相对命令。后续临时运行放runtime；完整开发历史在本地local_validation，未作为提交依赖。

目录可提交性、历史完整性及本地隔离检查见[整理检查](organization-check.json)。整理后仅更新CLI帮助及组件文档链接，并保留两项已有SDK故障检查；真实模型运行时的提示词与Agent决策逻辑未改。
