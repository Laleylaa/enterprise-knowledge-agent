"""One explicit smoke script, not a general offline question-answering model."""

import json

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

SMOKE_QUESTION = "国内差旅报销期限多久？"


def scripted_answer(messages, info, scenario):
    """Explicit offline writer consuming the same raw packet as the real writer."""
    if not any(t.name == "submit_answer" for t in info.output_tools):
        return None
    prompts = [p.content for m in messages if isinstance(m, ModelRequest)
               for p in m.parts if isinstance(p, UserPromptPart)]
    packet = json.loads(prompts[-1])
    sources = packet["sources"]
    selected = []
    for doc in (("D01", "D02") if scenario == "conflict" else ("D01",)):
        source = next((s for s in reversed(sources) if s["doc_id"] == doc
                       and "差旅报销须在行程结束后" in s["text"]), None)
        if source:
            selected.append(source)
    status, text, gaps, clarification = "incomplete", "MOCK_SCENARIO_UNSUPPORTED：实际原文不满足脚本前提。", ["需使用声明的固定资料。"], None
    refs = []
    if scenario == "missing":
        status, text, gaps = "unresolved", "本轮未取得 D99 原文，无法回答其规定；不据此断言制度不存在。", ["缺少 D99 原文。"]
    elif scenario == "tool_failure":
        text, gaps = "本轮工具执行失败，未能取得必要依据。", ["原文取得失败，当前查证未完成。"]
    elif scenario == "conflict" and len(selected) == 2 and all(
            f"差旅报销须在行程结束后 {days} 天内提交。" in s["text"]
            for s, days in zip(selected, (30, 15))):
        status, text, gaps = "needs_info", "两份原文分别规定30天与15天，当前脚本不选择适用制度。", ["缺少可核实的适用关系。"]
        clarification = "请提供适用制度或可核实的范围线索。"
        refs = [s["source_id"] for s in selected]
    elif scenario in {"normal", "recovery", "smoke"} and selected:
        expected = "国内差旅报销须在行程结束后 30 天内提交。"
        if expected in selected[0]["text"]:
            status, text, gaps, refs = "resolved", expected, [], [selected[0]["source_id"]]
    draft = dict(parts=[dict(text=text, source_ids=refs)], status=status, gaps=gaps,
                 clarification=clarification,
                 decision_summary="离线预设回答脚本依据程序交付原文，仅验证流程，不证明模型决策。")
    return ModelResponse(parts=[ToolCallPart("submit_answer", draft, tool_call_id="offline-answer")])


def _respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    written = scripted_answer(messages, info, "smoke")
    if written is not None:
        return written
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
    return ModelResponse(parts=[ToolCallPart("finish_research", {
        "reason": "sufficient" if hit else "blocked",
        "decision_summary": "离线预设脚本停止取证，原文由程序交付回答阶段。",
    }, tool_call_id="smoke-research")])


def create_smoke_model() -> FunctionModel:
    return FunctionModel(_respond, model_name="offline-smoke-script-v1")
