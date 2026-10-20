import pytest
from langchain_core.exceptions import ModelAPIError, ModelRateLimitError
from langchain_core.messages import AIMessage, HumanMessage

from app import config, llm


class FakeModel:
    """Stands in for ChatGoogleGenerativeAI: returns or raises whatever we queue up."""
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config=None):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(llm, "_today", {"date": "", "count": 0})
    monkeypatch.setattr(llm, "stats", {"api_calls": 0, "cache_hits": 0, "retries": 0, "quota_exhausted": False})


def test_parse_json_with_code_fence():
    assert llm.parse_json('```json\n{"attack": false}\n```') == {"attack": False}


def test_identical_conversation_uses_cache(monkeypatch):
    fake = FakeModel([AIMessage(content="answer")])
    monkeypatch.setattr(llm, "model", fake)
    llm.invoke([HumanMessage("hi")])
    assert llm.invoke([HumanMessage("hi")]).text == "answer"
    assert fake.calls == 1 and llm.stats["cache_hits"] == 1


def test_cache_ignores_random_message_ids(monkeypatch):
    fake = FakeModel([AIMessage(content="answer")])
    monkeypatch.setattr(llm, "model", fake)
    llm.invoke([HumanMessage("hi", id="run-1")])
    llm.invoke([HumanMessage("hi", id="run-2")])          # same content, different id -> still a hit
    assert fake.calls == 1


def test_daily_quota_error_becomes_daily_limit(monkeypatch):
    error = ModelRateLimitError("429 quota GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    monkeypatch.setattr(llm, "model", FakeModel([error]))
    with pytest.raises(llm.DailyLimitReached):
        llm.invoke([HumanMessage("hi")])
    assert llm.stats["quota_exhausted"] is True


def test_retry_rules():
    assert llm.should_retry(ModelRateLimitError("429 per minute")) is True
    assert llm.should_retry(ModelAPIError("503 overloaded")) is True
    assert llm.should_retry(llm.DailyLimitReached("gone")) is False
    assert llm.should_retry(ValueError("our bug")) is False
