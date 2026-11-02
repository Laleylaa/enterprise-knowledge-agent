# 业务端到端

`required/` 对应六类题目必验，`extended/` 是12项重要补充，均调用真实主模型。真实入口默认hybrid，明确指定时支持BM25/vector；两项hybrid专项在其他检索模式下跳过，跳过不会被evaluate视为完整通过。

`offline/` 只测试正式Mock BM25，不证明模型决策效果。执行上限通过Mock端到端的budget场景及基础预算检查共同验证，真实动态决策由真实业务记录独立证明。

共用运行器在 `../support/live.py`。不跨测试文件导入fixture；没有隐藏的本地测试依赖。详见[测试分层](../README.md)。
