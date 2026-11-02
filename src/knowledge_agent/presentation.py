"""Render recorded facts without selecting authoritative policies or inventing conclusions."""

from knowledge_agent.schemas import RunResult

LABELS = {"resolved": "已解决", "needs_info": "待补充信息", "unresolved": "未解决", "incomplete": "未完成"}


def render_result(result: RunResult) -> str:
    answer = result.result
    prose = "\n\n".join(p.text + "".join(f"[{n}]" for n in p.citation_numbers)
                          for p in answer.answer_parts) if answer.answer_parts else answer.answer
    status = LABELS[answer.status]
    if result.mode == "mock":
        status += "（离线 Mock，仅验证流程，不证明模型决策能力）"
    lines = [f"任务状态：{status}", f"\n回答：\n{prose}"]
    if answer.clarification:
        lines.append("请补充：" + answer.clarification)
    evidence = {e.evidence_id: e for e in result.observed_evidence}
    lines.append("\n引用：" + ("" if answer.citations else "无"))
    for number, citation in enumerate(answer.citations, 1):
        item = evidence[citation.evidence_id]
        lines.append(f"[{number}] {citation.doc_id}｜版本日期：{item.version_date}\n{citation.quote}")
    lines.append("\n资料缺口：" + ("；".join(answer.gaps) if answer.gaps else "无"))
    return "\n".join(lines)
