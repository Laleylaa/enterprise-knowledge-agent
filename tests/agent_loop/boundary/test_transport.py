"""Actual OpenAI SDK/provider with local HTTP injection, never a live service."""

import asyncio
import json

import httpx2
import pytest
from openai import AsyncOpenAI
from pydantic import SecretStr
from pydantic_ai import models

from knowledge_agent import model_adapter
from knowledge_agent.runtime import run_turn

pytestmark = pytest.mark.boundary


def completion(*, tool=False, malformed=False):
    args = {"query": "差旅", "purpose": "取得依据"} if tool else {
        "status": "needs_info", "answer": "请说明费用类型。", "citations": [],
        "gaps": ["费用类型不明。"], "clarification": "请说明费用类型。",
        "decision_summary": "本地 HTTP 注入响应。",
    }
    return {"id": "local-response", "object": "chat.completion", "created": 0, "model": "local-transport-contract",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None, "tool_calls": [{"id": "local-call", "type": "function",
                    "function": {"name": "search_knowledge" if tool else "submit_answer",
                                 "arguments": "{}" if malformed else json.dumps(args)}}]}}]}


@pytest.fixture
def http_run(loop_environment, monkeypatch, read_run_records):
    def run(replies, **overrides):
        settings, source = loop_environment
        settings = settings.model_copy(update={"mode": "real", "deepseek_api_key": SecretStr("local-test-key"),
                                                "base_url": "https://local.invalid/v1", **overrides})
        received, clients = [], []

        def respond(request):
            received.append(json.loads(request.content))
            assert len(received) <= len(replies), "Hidden SDK/framework request exceeded scripted responses"
            reply = replies[len(received) - 1]
            if isinstance(reply, Exception):
                raise reply
            if isinstance(reply, int):
                return httpx2.Response(reply, json={"error": {"message": "PRIVATE_PROVIDER_BODY", "type": "test"}})
            return httpx2.Response(200, json=reply)

        def client_factory(**kwargs):
            # Exercise production open_model, including its SDK retry setting.
            assert kwargs["max_retries"] == 0
            client = AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))
            clients.append(client)
            return client

        monkeypatch.setattr(model_adapter, "AsyncOpenAI", client_factory)
        monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)  # Socket/DNS remain blocked.
        result = asyncio.run(run_turn("费用问题", settings, source))
        records = read_run_records(settings, result)
        assert len(received) == result.usage.http_attempts
        assert clients and all(c.is_closed() for c in clients)
        assert "PRIVATE_PROVIDER_BODY" not in json.dumps(records)
        assert "local-test-key" not in json.dumps(records)
        assert result.mode == "real"
        return result, records, received
    return run


@pytest.mark.parametrize("failure", [429, 500, 502, 503, 504, httpx2.ConnectError("injected"), httpx2.ReadTimeout("injected")],
                         ids=["429", "500", "502", "503", "504", "connection", "read_timeout"])
def test_transient_error_retries_once_within_same_logical_turn(http_run, failure):
    result, records, requests = http_run([failure, completion()])
    assert result.termination_reason == "completed"
    assert result.usage.model_turns == 1 and result.usage.http_attempts == 2
    assert requests[0] == requests[1]
    assert [(r["model_turn"], r["attempt"]) for r in records["model-inputs"]] == [(1, 1), (1, 2)]


@pytest.mark.parametrize("status", [400, 401, 402, 404, 422, 501])
def test_nonrecoverable_error_is_not_retried_or_switched_to_mock(http_run, status):
    result, records, requests = http_run([status])
    assert result.termination_reason == "model_request_failed"
    assert result.result.status == "incomplete" and result.result_origin == "runtime_fallback"
    assert result.usage.model_turns == result.usage.http_attempts == 1
    assert not any(e["event_type"] == "model_request_retry" for e in records["trace"])


@pytest.mark.parametrize("retry", [0, 1])
def test_persistent_failure_never_exceeds_configured_transport_retries(http_run, retry):
    result, _, requests = http_run([503] * (retry + 1), transport_retries=retry)
    assert result.termination_reason == "model_request_failed"
    assert result.usage.model_turns == 1 and len(requests) == retry + 1


def test_http_cap_blocks_retry_before_wait_and_request(http_run):
    result, records, _ = http_run([429], max_http_attempts=1)
    assert result.termination_reason == "http_attempt_limit"
    assert result.usage.model_turns == result.usage.http_attempts == 1
    assert not any(e["event_type"] == "model_request_retry" for e in records["trace"])


@pytest.mark.parametrize("response,reason", [
    (completion(), "completed"), (completion(tool=True), "http_attempt_limit"),
    (completion(malformed=True), "http_attempt_limit"),
], ids=["last_http_final", "last_http_tool", "last_http_correction"])
def test_last_http_response_may_finish_but_cannot_start_more_work(http_run, response, reason):
    result, records, _ = http_run([response], max_http_attempts=1)
    assert result.termination_reason == reason
    assert result.usage.model_turns == result.usage.http_attempts == 1
    assert result.usage.tool_calls == 0 and records["tool-results"] == []


def test_output_correction_is_a_new_logical_turn(http_run):
    result, records, _ = http_run([completion(malformed=True), completion()])
    assert result.termination_reason == "completed"
    assert result.usage.model_turns == result.usage.http_attempts == 2
    assert [(r["model_turn"], r["attempt"]) for r in records["model-inputs"]] == [(1, 1), (2, 1)]
