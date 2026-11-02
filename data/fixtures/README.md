# 专项测试资料

本目录保存独立的场景快照，每次只加载一个 manifest。不同目录中的相同文档ID可代表不同测试版本，不能拼成一套知识库。保留现有目录名和正文，便于重现已有Trace；分类通过本索引说明。

## 业务端到端资料

| 分类 | 资料入口 | 设计重点 | 当前提交版用途 |
| --- | --- | --- | --- |
| 正常与信息不足 | [F1_single_rule](F1_single_rule/manifest.json) | 国内30天及申请状态；没有凭证要求 | 明确答案、改写、上下文、部分可答；Mock正常与故障流程 |
| 无法消解的冲突 | [F2_conflicting_rules](F2_conflicting_rules/manifest.json) | 30天与15天，同日期，无适用范围或优先级 | 必验冲突、通知线索不足、Mock冲突 |
| 冲突日期变体 | [F2_newer_D02](F2_newer_D02/manifest.json) | 只把D02日期改晚，不增加替代依据 | 不因日期较新擅自选15天 |
| 明确适用范围 | [F3_explicit_scope](F3_explicit_scope/manifest.json) | 国内30天、海外15天 | 保留的基础范围资料；当前精简E2E没有直接引用，旧回归使用 |
| 跨文档查证 | [F4_scope_evidence](F4_scope_evidence/manifest.json) | F2加D03，说明D01国内、D02海外 | 取得适用关系后依据对应条款回答 |
| 多主题与资料外问题 | [F5_leave_and_scope](F5_leave_and_scope/manifest.json) | F3加请假申请规则；没有育儿假天数 | 资料外问题、指代不足、国内转海外；也是业务知识库初始内容来源 |
| 原文替换 | [F6_replaced_rule](F6_replaced_rule/manifest.json) | F1的30改20，其余不变，日期也不变 | 旧对话不能压过本轮原文；这是受控内容替换，不是正式版本发布示例 |

测试位置：[题目必验](../../tests/e2e/required/test_acceptance.py)、[补充业务](../../tests/e2e/extended/test_business_edges.py)、[离线Mock](../../tests/e2e/offline/test_mock.py)。

## 工具边界资料

| 资料入口 | 设计重点 | 验证层级 |
| --- | --- | --- |
| [R1_section_context](R1_section_context/manifest.json) | 同一长章节开头写30天、后部限定仅国内；读取章节才能补全单块未含的上下文 | 基础读取、连接测试；也供真实hybrid降级E2E验证不误答海外30天 |

R1不是必须强制读取的脚本：真实Agent也可以通过补充检索取得范围证据。基础测试检查读取能力，业务测试检查最终证据与结论。见 [读取检查](../../tests/contracts/test_section_context.py) 和 [hybrid降级用例](../../tests/e2e/extended/test_hybrid_partial.py)。

工具失败、向量超时、模型连接失败、执行上限由测试控制，不写入制度正文。预期答案与故障计划也不进入知识库。
