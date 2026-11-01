"""Observe only the model→function call→tool→model boundary, without final-answer evaluation."""

import json

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

from knowledge_agent.agent import build_agent
from knowledge_agent.model_adapter import RecordedModel


def observations(messages):
    return [p for m in messages if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]


def acknowledgement():
    # The driver stops before this response enters final-answer handling.
    return ModelResponse(parts=[TextPart("工具观察已收到；测试在此停止，不生成业务回答。")])


def records(state, name):
    path = state.recorder.directory / f"{name}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


async def drive_tool_exchange(state, model, *, requests, origin):
    """Use the same composition as runtime.run_turn, stopping after observable feedback."""
    agent = build_agent(RecordedModel(model, state), state)
    question = json.loads((state.recorder.directory / "input.json").read_text())["question"]
    state.recorder.write("run.json", {"run_id": state.recorder.run_id, "stage": "agent_tool_calls",
                                     "model_origin": origin, "live_model": False,
                                     "boundary": "stop_after_tool_observation_no_final_answer"})
    async with agent.iter(question, deps=state, usage_limits=UsageLimits(request_limit=None)) as run:
        node = run.next_node
        for _ in range(30):
            node = await run.next(node)
            if state.usage.model_turns == requests and Agent.is_call_tools_node(node):
                assert all(isinstance(p, TextPart) for p in node.model_response.parts)
                assert run.result is None  # No end-to-end business result is produced.
                break
            assert not Agent.is_end_node(node), "Unexpected final answer in tool-only integration"
        else:
            raise AssertionError("Tool exchange did not reach the expected observation boundary")
    result = {"stage": "agent_tool_calls", "model_origin": origin, "live_model": False,
              "stopped_after": "tool_observation", "usage": state.usage.model_dump(),
              "tool_results": records(state, "tool-results")}
    assert result["tool_results"], "Successful tool observations must exist"
    assert not (state.recorder.directory / "output.json").exists(), "A bound tool overwrote turn output"
    state.recorder.event("test_observation_boundary", origin="test", model_origin=origin)
    state.recorder.write("output.json", result)
    state.recorder.write("tool-integration-evaluation.json", {
        "scope": "model_function_call_integration", "live_model": False,
        "model_origin": origin, "observed_requests": state.usage.model_turns,
        "tool_returns": len(result["tool_results"]), "final_business_answer_evaluated": False})
    return result
