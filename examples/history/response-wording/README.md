# 历史失败样例（提示词修订前）

此处原样保留3轮：通知冲突前置轮、通知追问和范围回答。原测试只核对结构及引用事实，自动通过后AI阅读发现两项口径缺陷：

- [通知追问](artifacts/e2e/outputs/quality_notification_r2/a579bd8fa0b54d069ed2e2efb38484b4/output.json)：“人事通知的说明不构成制度适用依据”过于绝对，应限定为当前缺少可核实依据。
- [国内期限](artifacts/e2e/outputs/quality_scope_r2/127b4a9037df43b88e98ea5f3880eb0e/output.json)：附加海外15天。引用齐全，但超出当前问题。

随后补充了通用口径约束。这里是明确选取的失败说明，不是当前代码全量结果；当前结果见[提交版证据索引](../../README.md)。原始完整历史批次和原测试保留在本地归档中。

原始字节没有修改，[selection.json](selection.json)记录来源批次和文件SHA-256；历史Trace中的绝对路径只表示原运行位置，评审用本目录相对路径。历史测试路径随整理已迁移，旧自动报告不回填。
