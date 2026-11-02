"""Single-turn audit and explicit test-only backend failure injection.

Expected outcomes and fault plans are never passed to the model/runtime prompt.
"""

import json
from dataclasses import dataclass, field

from knowledge_agent.reading.tool import ReadTool
from knowledge_agent.retrieval.tool import SearchTool


# Included in archived reports so automated green cannot silently close semantic work.
SEMANTIC_REVIEW_CHECKS = [
    "Answer conclusions and conditions are supported by the cited original text, including negation and numbers.",
    "Conflicts remain unresolved unless observed source evidence establishes applicability; user claims are not evidence.",
    "History and notification details are represented faithfully; no inferred channel or stale condition.",
    "Gaps and clarification concern the current question; actual tool failures are explained honestly.",
    "Status matches what was answered or prevented; concision/wording notes are separate from business defects.",
]


def read_jsonl(directory, name):
    path = directory / f"{name}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@dataclass
class ToolFaultPlan:
    mode: str = "none"
    targets: tuple[str, ...] = ("search_knowledge", "read_document")
    attempts: int = 0
    injected: list[dict] = field(default_factory=list)

    def install(self, monkeypatch):
        assert self.mode in {"none", "always", "first"}
        for cls in (SearchTool, ReadTool):
            if cls.name not in self.targets:
                continue
            original = cls.execute

            def execute(tool, arguments, *, call_id, original=original):
                with monkeypatch.context() as patch:
                    self._inject(tool, call_id, patch)
                    return original(tool, arguments, call_id=call_id)

            monkeypatch.setattr(cls, "execute", execute)
            if cls is SearchTool:
                original_async = cls.aexecute

                async def aexecute(tool, arguments, *, call_id, deadline=None, original=original_async):
                    with monkeypatch.context() as patch:
                        self._inject(tool, call_id, patch)
                        return await original(tool, arguments, call_id=call_id, deadline=deadline)

                monkeypatch.setattr(cls, "aexecute", aexecute)

    def _inject(self, tool, call_id, patch):
        self.attempts += 1
        inject = self.mode == "always" or (self.mode == "first" and self.attempts == 1)
        if not inject:
            return
        record = {"tool": tool.name, "tool_call_id": call_id, "execution_number": self.attempts,
                  "injection": "test_backend_oserror"}
        self.injected.append(record)
        tool.recorder.event("test_fault_injected", origin="test", **record)
        def fail(*args, **kwargs):
            raise OSError("test-only backend failure")
        if isinstance(tool, SearchTool):
            # Q14 is a whole search-tool fault; hybrid's partial branch faults have separate tests.
            backends = getattr(tool.index, 'backends', {tool.strategy: tool.index})
            for index in backends.values():
                for method in ('rank', 'arank'):
                    if hasattr(index, method):
                        patch.setattr(index, method, fail)
            patch.setattr(tool.index, 'lookup', fail)
        else:
            patch.setattr(tool, '_select', fail)

    def snapshot(self):
        return {"origin": "test_only", "mode": self.mode, "targets": self.targets, "executions": self.attempts,
                "injections": self.injected, "visible_to_model": "only_actual_tool_error"}


def audit_run(directory, result, *, expected_history=None, expected_retrieval="bm25"):
    """Check transport/trace/citation facts, not whether prose supports a conclusion."""
    assert json.loads((directory / "output.json").read_text()) == result
    requests = read_jsonl(directory, "model-inputs")
    events = read_jsonl(directory, "trace")
    returns = read_jsonl(directory, "tool-results")
    assert events[-1]["event_type"] == "final_result"
    assert result["stage"] == "tool_integration" and result["requested_retrieval"] == expected_retrieval
    assert json.loads((directory / "input.json").read_text())["effective_history"] == (expected_history or [])
    for request in requests:
        names = {t["name"] for t in request["tools"]}
        if request["phase"] == "research":
            assert names == {"search_knowledge", "read_document", "finish_research"}
        else:
            assert request["phase"] == "answer"
            assert names in ({"submit_answer"}, {"submit_answer", "request_evidence"})
            # A fresh writer context must not inherit collector prose or tool chatter.
            first_parts = [p for p in request["messages"][0]["parts"] if p["part_kind"] != "system-prompt"]
            assert len(first_parts) == 1 and first_parts[0]["part_kind"] == "user-prompt"
            packet = json.loads(first_parts[0]["content"])
            assert packet["kind"] == "answer_input"
            assert packet["question"] == json.loads((directory / "input.json").read_text())["question"]
            assert packet["history"] == [{"role": h["role"], "content": h["content"]}
                                         for h in expected_history or []]
            items = {e["evidence_id"]: e for e in result["observed_evidence"]}
            for source in packet["sources"]:
                item = items[source["evidence_id"]]
                assert item["delivered_to_model"] and source["doc_id"] == item["doc_id"]
                assert any(source["text"] == span["text"] and source["start"] == span["start"]
                           and source["end"] == span["end"] for span in item["source_spans"])
    evidence = {e["evidence_id"]: e for e in result["observed_evidence"]}
    for citation in result["result"]["citations"]:
        item = evidence[citation["evidence_id"]]
        assert item["delivered_to_model"] and item["doc_id"] == citation["doc_id"]
        assert any(citation["quote"] in span["text"] for span in item["source_spans"])
    observed_ids = set()
    for request in requests:
        for message in request["messages"]:
            for part in message["parts"]:
                if part.get("part_kind") == "tool-return" and isinstance(part.get("content"), dict):
                    value = part["content"]
                    if value.get("schema_version") == 1:
                        assert value in returns
                        assert part["tool_call_id"] == value["tool_call_id"]
                        observed_ids.add(part["tool_call_id"])
    reused_ids = set()
    reused_path = directory / 'session-evidence.json'
    if reused_path.exists():
        packet = json.loads(reused_path.read_text())
        encoded = json.dumps(packet, ensure_ascii=False)
        delivered = any(p.get('part_kind') == 'user-prompt' and p.get('content') == encoded
                        for r in requests for m in r['messages'] for p in m['parts'])
        corpus = json.loads((directory / 'corpus.json').read_text())
        documents = {d['doc_id']: d for d in corpus['documents']}
        for item in packet['sources']:
            assert item['reused_from'] and item['corpus_hash'] == corpus['corpus_hash']
            document = documents[item['doc_id']]
            assert all(document['body'][s['start']:s['end']] == s['text'] for s in item['source_spans'])
            if delivered:
                reused_ids.add(item['evidence_id'])
    assert all(not e["delivered_to_model"] or
               (e['evidence_id'] in reused_ids if e.get('reused_from') else e['tool_call_id'] in observed_ids)
               for e in evidence.values())
    if result["termination_reason"] == "completed":
        assert all(r["tool_call_id"] in observed_ids for r in returns)
        assert any(e["event_type"] == "result_candidate" for e in events)
    return {"requests": requests, "events": events, "returns": returns}


def delivered_rules(request):
    found = set()
    for message in request["messages"]:
        for part in message["parts"]:
            value = part.get("content")
            if part.get("part_kind") != "tool-return" or not isinstance(value, dict):
                continue
            for item in value.get("data", {}).get("hits", []) + value.get("data", {}).get("segments", []):
                if item["doc_id"] == "D01" and "30 天" in item["text"]:
                    found.add("D01")
                if item["doc_id"] == "D02" and "15 天" in item["text"]:
                    found.add("D02")
    return found


def evaluate_case(case, result, records, fault):
    """Observable requirements only; semantic review remains separately recorded."""
    answer = result["result"]
    quotes = "\n".join(c["quote"] for c in answer["citations"])
    checks = {"model_final_result": result["result_origin"] == "model" and result["termination_reason"] == "completed"}
    if case == "Q01":
        checks.update(status=answer["status"] == "resolved",
                      cited_condition=all(s in quotes for s in ["国内", "行程结束", "30 天"]),
                      cited_source={c["doc_id"] for c in answer["citations"]} == {"D01"})
    elif case == "Q02":
        both_turns = [r["model_turn"] for r in records["requests"] if delivered_rules(r) == {"D01", "D02"}]
        stop_reasons = [e["payload"]["result"]["reason"] for e in records["events"]
                        if e["event_type"] == "research_complete"]
        checks.update(status=answer["status"] == "needs_info", clarification=bool(answer["clarification"]),
                      conflict_evidence_state=bool(stop_reasons) and all(r == "conflict" for r in stop_reasons),
                      both_quotes=all(s in quotes for s in ["30 天", "15 天"]),
                      both_sources={c["doc_id"] for c in answer["citations"]} == {"D01", "D02"},
                      both_rules_observed=bool(both_turns),
                      further_check_after_conflict=bool(both_turns) and any(
                          e["event_type"] == "tool_requested" and e["payload"]["model_turn"] >= min(both_turns)
                          for e in records["events"]))
    elif case == "Q14a":
        checks.update(status=answer["status"] == "incomplete", no_invented_citations=not answer["citations"],
                      no_evidence=not result["observed_evidence"], fault_exercised=bool(fault.injected),
                      all_tools_failed=bool(records["returns"]) and all(r["status"] == "error" for r in records["returns"]))
    elif case == "Q14b":
        failed = [r for r in records["returns"] if r["status"] == "error"]
        error_turns = [r["model_turn"] for r in records["requests"] if any(
            p.get("part_kind") == "tool-return" and p.get("tool_call_id") in {x["tool_call_id"] for x in failed}
            for m in r["messages"] for p in m["parts"])]
        recovered = answer["status"] == "resolved" and "30 天" in quotes
        checks.update(single_injection=len(fault.injected) == 1,
                      basic_status=answer["status"] in {"incomplete", "resolved"},
                      recovered=recovered,
                      model_action_after_error=bool(error_turns) and any(
                          e["event_type"] == "tool_requested" and e["payload"]["model_turn"] >= min(error_turns)
                          for e in records["events"]))
    else:
        raise ValueError(case)
    return {"case_id": case, "automatic_checks": checks,
            "automatic_pass": all(checks.values()),
            "semantic_review": "pending_separate_review",
            "automated_scope": "structure_evidence_execution",
            "required_semantic_checks": SEMANTIC_REVIEW_CHECKS,
            "note": "Exact quotes and event order do not prove semantic correctness; Q14b recovery is a separate capability."}
