"""Real SDK/provider wire protocol with local HTTP responses; no live API or final answer."""

import asyncio
import json

import httpx2
import pytest
from openai import AsyncOpenAI
from pydantic import SecretStr
from pydantic_ai import models

from knowledge_agent import model_adapter
from tests.support.tool_calls import drive_tool_exchange, records

pytestmark = pytest.mark.contract


def completion(number, *, name=None, args=None, call_id=None):
    message = {"role": "assistant", "content": "工具观察已收到；本测试不生成业务回答。"}
    if name:
        message.update(content=None, tool_calls=[{"id": call_id, "type": "function", "function": {
            "name": name, "arguments": json.dumps(args, ensure_ascii=False)}}])
    return {"id": f"local-fc-response-{number}", "object": "chat.completion", "created": 0,
            "model": "local-function-call-contract", "choices": [{"index": 0,
                "finish_reason": "tool_calls" if name else "stop", "message": message}]}


@pytest.mark.parametrize("chain", [True], ids=["search_then_section_read"])
def test_sdk_sends_native_definitions_and_returns_with_matching_call_ids(bound_state, monkeypatch, chain):
    state = bound_state("fc_http_search_read" if chain else "fc_http_direct_read", "R1_section_context",
                        mode="real", deepseek_api_key=SecretStr("local-test-not-a-live-key"),
                        base_url="https://local.invalid/v1")
    received, clients = [], []

    def transport(request):
        body = json.loads(request.content)
        received.append(body)
        state.recorder.append("provider-requests.jsonl", {"transport": "local_http_injection", "body": body})
        definitions = body["tools"]
        assert all(t["type"] == "function" for t in definitions)
        functions = {t["function"]["name"]: t["function"] for t in definitions}
        assert set(functions) == {"search_knowledge", "read_document", "submit_answer"}
        for name, properties, required in [
            ("search_knowledge", {"query", "purpose", "doc_ids", "limit", "cursor"}, {"query", "purpose"}),
            ("read_document", {"doc_id", "purpose", "section_id", "chunk_id", "cursor"}, {"doc_id", "purpose"}),
        ]:
            function = functions[name]
            assert function["description"]
            assert set(function["parameters"]["properties"]) == properties
            assert set(function["parameters"]["required"]) == required
            assert function["parameters"]["additionalProperties"] is False
            assert all(p.get("description") for p in function["parameters"]["properties"].values())
        assert functions["search_knowledge"]["parameters"]["properties"]["limit"]["maximum"] == 10
        number = len(received)
        if number == 1:
            assert not any(m["role"] == "tool" for m in body["messages"])
            name = "search_knowledge" if chain else "read_document"
            args = ({"query": "草稿保存时间", "purpose": "查条款", "limit": 1} if chain else
                    {"doc_id": "D10", "chunk_id": "D10-C0002", "purpose": "读取原文块"})
            response = completion(number, name=name, args=args, call_id="provider-call-1")
        else:
            messages = [m for m in body["messages"] if m["role"] == "tool"]
            returns = records(state, "tool-results")
            assert len(messages) == len(returns)
            for message, returned in zip(messages, returns):
                assert message["tool_call_id"] == returned["tool_call_id"]
                assert json.loads(message["content"]) == returned
                assert returned["status"] == "ok"
            if number == 2 and chain:
                hit = returns[-1]["data"]["hits"][0]
                response = completion(number, name="read_document", args={
                    "doc_id": hit["doc_id"], "section_id": hit["section_id"], "purpose": "按来源读取章节"},
                    call_id="provider-call-2")
            else:
                assert number == (3 if chain else 2)
                response = completion(number)
        state.recorder.append("provider-responses.jsonl", {"transport": "local_http_injection", "body": response})
        return httpx2.Response(200, json=response)

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        client = AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(transport)))
        clients.append(client)
        return client

    monkeypatch.setattr(model_adapter, "AsyncOpenAI", factory)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)  # Socket and DNS remain blocked.
    async def run():
        async with model_adapter.open_model(state.settings) as model:
            return await drive_tool_exchange(state, model, requests=3 if chain else 2, origin="local_http_injection")
    result = asyncio.run(run())
    assert result["usage"]["http_attempts"] == len(received) == (3 if chain else 2)
    assert clients and all(client.is_closed() for client in clients)
    assert all(e.delivered_to_model for e in state.evidence.snapshot())
    assert not any(e["event_type"] == "final_result" for e in records(state, "trace"))
    assert "local-test-not-a-live-key" not in "".join(p.read_text() for p in state.recorder.directory.iterdir())
