# Agent 工具调用集成验证

本组测试只覆盖模型请求携带工具定义 → FC 参数校验与分发 → 执行真实本地工具 → 结果进入下一次模型请求。测试在收到工具观察后停止，不生成或评估最终业务回答，不属于 E2E。

12 项使用受控 FunctionModel；2 项通过生产 open_model、DeepSeekProvider 和 OpenAI SDK，以本地 HTTP MockTransport 注入标准 tool_calls 响应。全部阻断外网并标记 live_model=false；这些结果证明接入契约与结果回传，不证明真实模型的自主决策质量。

每次请求都校验工具 name、description 和参数 JSON Schema；工具名为 search_knowledge 与 read_document。参数复用 SearchRequest、ReadRequest，工具共享本轮语料快照、证据和 Trace。

## 运行结果

- [FunctionModel：12 passed](reports/tool_calls/function-binding-results.xml)
- [原生 FC 协议：2 passed](reports/tool_calls/provider-function-results.xml)
- [已有组件回归：156 passed，1 skipped](reports/tool_calls/existing-components-regression.xml)；跳过项需要显式启用真实 API。

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/tool_calls -q --examples-dir=examples
```

## 输入、实际输出与记录

output.json 是本次调用的实际工具返回与调用计数摘要，不是 Answer。Trace 记录调用事件，model-inputs.jsonl 可核对工具返回是否完整进入下一次模型输入。每个运行的 artifacts.json 保存文件路径与 SHA-256。

| 场景 | 输入 | 实际输出 | 调用记录 | 模型输入 | 清单 |
|---|---|---|---|---|---|
| 关键词检索，返回 D01 原文块 | [输入](inputs/fc_search_D01/ea3669e977c14e26a0d87630510a5714/input.json) | [输出](outputs/fc_search_D01/ea3669e977c14e26a0d87630510a5714/output.json) | [Trace](traces/fc_search_D01/ea3669e977c14e26a0d87630510a5714/trace.jsonl) | [模型输入](traces/fc_search_D01/ea3669e977c14e26a0d87630510a5714/model-inputs.jsonl) | [SHA-256](traces/fc_search_D01/ea3669e977c14e26a0d87630510a5714/artifacts.json) |
| 空查询 + 文档 ID 定位 D02 | [输入](inputs/fc_search_D02/44d88af87b654b77b1c3e42856d9fbc6/input.json) | [输出](outputs/fc_search_D02/44d88af87b654b77b1c3e42856d9fbc6/output.json) | [Trace](traces/fc_search_D02/44d88af87b654b77b1c3e42856d9fbc6/trace.jsonl) | [模型输入](traces/fc_search_D02/44d88af87b654b77b1c3e42856d9fbc6/model-inputs.jsonl) | [SHA-256](traces/fc_search_D02/44d88af87b654b77b1c3e42856d9fbc6/artifacts.json) |
| 直接读取全文 | [输入](inputs/fc_read_document/5d6eeec88add4aa7ab16856428106283/input.json) | [输出](outputs/fc_read_document/5d6eeec88add4aa7ab16856428106283/output.json) | [Trace](traces/fc_read_document/5d6eeec88add4aa7ab16856428106283/trace.jsonl) | [模型输入](traces/fc_read_document/5d6eeec88add4aa7ab16856428106283/model-inputs.jsonl) | [SHA-256](traces/fc_read_document/5d6eeec88add4aa7ab16856428106283/artifacts.json) |
| 直接读取指定章节 | [输入](inputs/fc_read_section/3bdbe2ccf1d64780a1d5ab9f0fd3ad62/input.json) | [输出](outputs/fc_read_section/3bdbe2ccf1d64780a1d5ab9f0fd3ad62/output.json) | [Trace](traces/fc_read_section/3bdbe2ccf1d64780a1d5ab9f0fd3ad62/trace.jsonl) | [模型输入](traces/fc_read_section/3bdbe2ccf1d64780a1d5ab9f0fd3ad62/model-inputs.jsonl) | [SHA-256](traces/fc_read_section/3bdbe2ccf1d64780a1d5ab9f0fd3ad62/artifacts.json) |
| 直接读取指定块 | [输入](inputs/fc_read_chunk/2ed9fed64628468ea37dad00fd949dd9/input.json) | [输出](outputs/fc_read_chunk/2ed9fed64628468ea37dad00fd949dd9/output.json) | [Trace](traces/fc_read_chunk/2ed9fed64628468ea37dad00fd949dd9/trace.jsonl) | [模型输入](traces/fc_read_chunk/2ed9fed64628468ea37dad00fd949dd9/model-inputs.jsonl) | [SHA-256](traces/fc_read_chunk/2ed9fed64628468ea37dad00fd949dd9/artifacts.json) |
| 根据检索命中的章节定位扩大上下文 | [输入](inputs/fc_search_read_section/d7e2a2d763844b74afdb43920dd34001/input.json) | [输出](outputs/fc_search_read_section/d7e2a2d763844b74afdb43920dd34001/output.json) | [Trace](traces/fc_search_read_section/d7e2a2d763844b74afdb43920dd34001/trace.jsonl) | [模型输入](traces/fc_search_read_section/d7e2a2d763844b74afdb43920dd34001/model-inputs.jsonl) | [SHA-256](traces/fc_search_read_section/d7e2a2d763844b74afdb43920dd34001/artifacts.json) |
| 根据返回的 cursor 继续取下一页 | [输入](inputs/fc_search_pagination/12b1e6abc3734455ac7606c6d16f32fe/input.json) | [输出](outputs/fc_search_pagination/12b1e6abc3734455ac7606c6d16f32fe/output.json) | [Trace](traces/fc_search_pagination/12b1e6abc3734455ac7606c6d16f32fe/trace.jsonl) | [模型输入](traces/fc_search_pagination/12b1e6abc3734455ac7606c6d16f32fe/model-inputs.jsonl) | [SHA-256](traces/fc_search_pagination/12b1e6abc3734455ac7606c6d16f32fe/artifacts.json) |
| 章节超限后按返回的 read_args 读取局部块 | [输入](inputs/fc_read_local_locator/e561d1bfbd2b4e7e993cee082041411b/input.json) | [输出](outputs/fc_read_local_locator/e561d1bfbd2b4e7e993cee082041411b/output.json) | [Trace](traces/fc_read_local_locator/e561d1bfbd2b4e7e993cee082041411b/trace.jsonl) | [模型输入](traces/fc_read_local_locator/e561d1bfbd2b4e7e993cee082041411b/model-inputs.jsonl) | [SHA-256](traces/fc_read_local_locator/e561d1bfbd2b4e7e993cee082041411b/artifacts.json) |
| 同一响应提出两个调用，分别关联正确 call ID | [输入](inputs/fc_two_tools_one_response/91b12fb69b2f47a9adaeb49921f5d226/input.json) | [输出](outputs/fc_two_tools_one_response/91b12fb69b2f47a9adaeb49921f5d226/output.json) | [Trace](traces/fc_two_tools_one_response/91b12fb69b2f47a9adaeb49921f5d226/trace.jsonl) | [模型输入](traces/fc_two_tools_one_response/91b12fb69b2f47a9adaeb49921f5d226/model-inputs.jsonl) | [SHA-256](traces/fc_two_tools_one_response/91b12fb69b2f47a9adaeb49921f5d226/artifacts.json) |
| 拒绝非法 limit，反馈后接受修正调用 | [输入](inputs/fc_argument_correction_limit/524ba3a2fae14f5abb80f6ceaf9e2298/input.json) | [输出](outputs/fc_argument_correction_limit/524ba3a2fae14f5abb80f6ceaf9e2298/output.json) | [Trace](traces/fc_argument_correction_limit/524ba3a2fae14f5abb80f6ceaf9e2298/trace.jsonl) | [模型输入](traces/fc_argument_correction_limit/524ba3a2fae14f5abb80f6ceaf9e2298/model-inputs.jsonl) | [SHA-256](traces/fc_argument_correction_limit/524ba3a2fae14f5abb80f6ceaf9e2298/artifacts.json) |
| 拒绝空查询且无文档 ID，反馈后接受修正调用 | [输入](inputs/fc_argument_correction_ids/258c2d6f87d6446684a5c57f58c7b5dc/input.json) | [输出](outputs/fc_argument_correction_ids/258c2d6f87d6446684a5c57f58c7b5dc/output.json) | [Trace](traces/fc_argument_correction_ids/258c2d6f87d6446684a5c57f58c7b5dc/trace.jsonl) | [模型输入](traces/fc_argument_correction_ids/258c2d6f87d6446684a5c57f58c7b5dc/model-inputs.jsonl) | [SHA-256](traces/fc_argument_correction_ids/258c2d6f87d6446684a5c57f58c7b5dc/artifacts.json) |
| 拒绝同时指定章节与块，反馈后接受修正调用 | [输入](inputs/fc_argument_correction_selector/c9259b476a7f4c2e8c8fb9222847aa49/input.json) | [输出](outputs/fc_argument_correction_selector/c9259b476a7f4c2e8c8fb9222847aa49/output.json) | [Trace](traces/fc_argument_correction_selector/c9259b476a7f4c2e8c8fb9222847aa49/trace.jsonl) | [模型输入](traces/fc_argument_correction_selector/c9259b476a7f4c2e8c8fb9222847aa49/model-inputs.jsonl) | [SHA-256](traces/fc_argument_correction_selector/c9259b476a7f4c2e8c8fb9222847aa49/artifacts.json) |
| 原生 HTTP FC：直接读取并回传 role=tool 结果 | [输入](inputs/fc_http_direct_read/9c3fd0d6ed984e659b432d3d1eb73f61/input.json) | [输出](outputs/fc_http_direct_read/9c3fd0d6ed984e659b432d3d1eb73f61/output.json) | [Trace](traces/fc_http_direct_read/9c3fd0d6ed984e659b432d3d1eb73f61/trace.jsonl) | [模型输入](traces/fc_http_direct_read/9c3fd0d6ed984e659b432d3d1eb73f61/model-inputs.jsonl) | [SHA-256](traces/fc_http_direct_read/9c3fd0d6ed984e659b432d3d1eb73f61/artifacts.json) |
| 原生 HTTP FC：检索→按章节读取→回传结果 | [输入](inputs/fc_http_search_read/d31c5e4264194a31be965a0abe8fb6e8/input.json) | [输出](outputs/fc_http_search_read/d31c5e4264194a31be965a0abe8fb6e8/output.json) | [Trace](traces/fc_http_search_read/d31c5e4264194a31be965a0abe8fb6e8/trace.jsonl) | [模型输入](traces/fc_http_search_read/d31c5e4264194a31be965a0abe8fb6e8/model-inputs.jsonl) | [SHA-256](traces/fc_http_search_read/d31c5e4264194a31be965a0abe8fb6e8/artifacts.json) |

## 原生 HTTP 请求与响应

以下仅保存请求和响应正文，不保存认证请求头；使用测试假密钥与本地注入响应。

- 原生 HTTP FC：直接读取并回传 role=tool 结果：[请求正文](traces/fc_http_direct_read/9c3fd0d6ed984e659b432d3d1eb73f61/provider-requests.jsonl)、[响应正文](traces/fc_http_direct_read/9c3fd0d6ed984e659b432d3d1eb73f61/provider-responses.jsonl)。

- 原生 HTTP FC：检索→按章节读取→回传结果：[请求正文](traces/fc_http_search_read/d31c5e4264194a31be965a0abe8fb6e8/provider-requests.jsonl)、[响应正文](traces/fc_http_search_read/d31c5e4264194a31be965a0abe8fb6e8/provider-responses.jsonl)。

已覆盖成功检索、读取三个范围、跨工具定位、分页、内容超限后的局部读取、同轮多个调用、非法参数修正及原生协议序列化。未覆盖真实模型效果、最终引用回答、六项业务验收 E2E、长耗时同步工具的强制中断。
