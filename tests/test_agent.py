import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from app import agent, llm


@tool
def add(a: float, b: float) -> dict:
    """Add two numbers."""
    return {"sum": a + b}


@tool
def broken(years: int) -> dict:
    """Always fails."""
    raise ValueError("years must be between 1 and 70")


def call(name, args, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


def fake_llm(monkeypatch, replies):
    """Replace the LLM with scripted replies; returns the list of messages it was shown last."""
    seen = []

    def fake_invoke(messages, tools=None, name=""):
        seen.append(messages[-1])
        return replies.pop(0)

    monkeypatch.setattr(llm, "invoke", fake_invoke)
    return seen


def test_agent_calls_tool_then_answers(monkeypatch):
    seen = fake_llm(monkeypatch, [call("add", {"a": 2, "b": 3}), AIMessage(content="The sum is 5")])
    assert agent.run_agent("calc", "be a calculator", "2+3?", [add]) == "The sum is 5"
    assert "5" in seen[1].content                      # the tool result was sent back to the model


def test_tool_error_goes_back_to_the_model(monkeypatch):
    seen = fake_llm(monkeypatch, [call("broken", {"years": 0}), AIMessage(content="I used an invalid value")])
    agent.run_agent("x", "y", "z", [broken])
    assert "years must be between 1 and 70" in seen[1].content


def test_agent_stops_at_recursion_limit(monkeypatch):
    monkeypatch.setattr(llm, "invoke", lambda messages, tools=None, name="": call("add", {"a": 1, "b": 1}))
    with pytest.raises(GraphRecursionError):
        agent.run_agent("loop", "x", "y", [add])
