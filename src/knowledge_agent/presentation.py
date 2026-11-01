"""Render recorded facts without selecting authoritative policies or inventing conclusions."""

from knowledge_agent.schemas import RunResult

LABELS = {"resolved": "已解决", "needs_info": "待补充信息", "unresolved": "未解决", "incomplete": "未完成"}


def render_result(result: RunResult, *, include_observed: bool = True) -> str:
    answer = result.result
    lines = [f"任务状态：{LABELS[answer.status]}（{answer.status}）", answer.answer]
    if answer.status == "incomplete":
        lines.insert(1, f"中断原因：{result.termination_reason}")
    if result.mode == "mock" and result.mock_scenario:
        lines.insert(0, f"运行方式：离线预设脚本（{result.mock_scenario}），仅验证流程，不证明模型决策能力。")
    evidence = {e.evidence_id: e for e in result.observed_evidence}
    lines.append("\n引用与已取得资料")
    for citation in answer.citations:
        item = evidence[citation.evidence_id]
        spans = item.source_spans or [item]
        span = next(s for s in spans if citation.quote in s.text)
        start = span.start + span.text.index(citation.quote)
        lines.append(f"引用 {citation.doc_id}｜{item.version_date}｜字符 [{start}, {start + len(citation.quote)})｜{citation.evidence_id}\n{citation.quote}")
    if not answer.citations and result.observed_evidence and include_observed:
        lines.append("尚无最终结论引用；以下为本轮已取得、尚未完成判断的原文。")
    elif not answer.citations:
        lines.append("本轮无最终结论引用。")
    if include_observed:
        seen = set()
        for item in result.observed_evidence:
            for span in item.source_spans or [item]:
                key = (item.doc_id, item.content_hash, span.start, span.end)
                if key in seen:
                    continue
                seen.add(key)
                delivered = "已反馈模型" if item.delivered_to_model else "已取得，尚未反馈模型"
                lines.append(f"已取得原文 {item.doc_id}｜{item.version_date}｜字符 [{span.start}, {span.end})｜{delivered}\n{span.text}")
        if not result.observed_evidence and not answer.citations:
            lines.append("本轮未取得可展示的原文依据。")
        if answer.status == "incomplete" and result.action_summaries:
            lines.append("模型此前行动说明（请求目的，查证未完成；不代表已形成结论）：")
            for action in result.action_summaries:
                lines.append(f"- {action['tool']}：{action['purpose']}")
    lines.append("\n资料缺口：" + ("；".join(answer.gaps) if answer.gaps else "无已声明缺口"))
    if answer.clarification:
        lines.append("请补充：" + answer.clarification)
    return "\n".join(lines)
