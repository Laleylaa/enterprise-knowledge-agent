# 验证材料

[最新完整提交包](submission-check/README.md)包含当前代码全部49项测试结果：49项通过、0失败、0错误、0跳过，以及23轮真实回答、28条引用。另附4个冲突与适用关系用例各3次的[定向复测](submission-check/repeat-check/README.md)，12次均通过，单独计数。历史批次留在本地，本目录保留当前版本材料。

- [测试结果](submission-check/results.xml)、[汇总](submission-check/summary.json)
- [每轮输入、实际输出与Trace](submission-check/cases.md)
- [测试预期、实际结果与限制](../docs/03-evaluation.md)

每轮三份文件，共用资料按版本保存。Trace由真实日志提取，包含模型动作、工具参数、返回摘要、失败和后续处理；答案及引用内容保持原值。重复提示词、工具定义和HTTP调试报文留在本地。

`pytest --examples-dir`、`evaluate`及统一打包脚本使用相同导出规则，复跑命令见[材料说明](submission-check/README.md)。
