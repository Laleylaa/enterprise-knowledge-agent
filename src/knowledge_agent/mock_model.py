"""One explicit smoke script, not a general offline question-answering model."""

import json

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

SMOKE_QUESTION = "国内差旅报销期限多久？"


def _respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    observations = [part for message in messages if isinstance(message, ModelRequest)
                    for part in message.parts if isinstance(part, ToolReturnPart)]
    if not observations:
        return ModelResponse(parts=[ToolCallPart("search_knowledge", {
            "query": "国内差旅 报销 期限", "purpose": "离线预设脚本：取得冒烟资料"
        }, tool_call_id="smoke-search")])

    content = observations[-1].content
    if isinstance(content, str):
        content = json.loads(content)
    hits = content.get("data", {}).get("hits", []) if isinstance(content, dict) else []
    # Match the explicit script premise, never invent a successful observation.
    expected = "国内差旅报销须在行程结束后 30 天内提交。"
    hit = next((item for item in hits if item["doc_id"] == "D01" and item["text"] == expected), None)
    if hit is None:
        answer = {"status": "incomplete", "answer": "MOCK_SCENARIO_UNSUPPORTED：实际资料不满足冒烟脚本前提。",
                  "citations": [], "gaps": ["需要使用声明的冒烟资料和输入。"],
                  "clarification": None, "decision_summary": "预设脚本不适用于当前工具结果。"}
    else:
        answer = {"status": "resolved", "answer": hit["text"],
                  "citations": [{"evidence_id": hit["evidence_id"], "doc_id": hit["doc_id"], "quote": hit["text"]}],
                  "gaps": [], "clarification": None,
                  "decision_summary": "离线预设脚本依据实际工具返回构造结果，仅验证程序流程。"}
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, answer, tool_call_id="smoke-answer")])


def create_smoke_model() -> FunctionModel:
    return FunctionModel(_respond, model_name="offline-smoke-script-v1")
