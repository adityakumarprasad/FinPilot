"""The ONLY place that talks to Gemini (through LangChain).
Free-tier protection: cache -> daily budget -> pacing (rate limiter). Retries: LangGraph RetryPolicy."""
import hashlib
import json
import logging
import os
import warnings
from datetime import date

from langchain_core._api.beta_decorator import LangChainBetaWarning
from langchain_core.exceptions import ModelAPIError, ModelRateLimitError
from langchain_core.load import dumps, loads
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import RetryPolicy

from app import config

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=LangChainBetaWarning)   # langchain_core.load is marked beta

model = ChatGoogleGenerativeAI(
    model=config.LLM_MODEL,
    google_api_key=config.GEMINI_API_KEY or "not-set",   # placeholder so imports/tests work without a key
    max_retries=0,           # retries are LangGraph's job (RETRY_POLICY below), so the behaviour is visible
    timeout=90,
    rate_limiter=InMemoryRateLimiter(                    # pacing: at most 1 request every N seconds
        requests_per_second=1 / config.SECONDS_BETWEEN_CALLS, check_every_n_seconds=0.2, max_bucket_size=1),
)

stats = {"api_calls": 0, "cache_hits": 0, "retries": 0, "quota_exhausted": False}
_today = {"date": "", "count": 0}

RETRYABLE = (ModelRateLimitError, ModelAPIError)    # per-minute limits and server errors (5xx)


class DailyLimitReached(Exception):
    pass


def _check_daily_limit():
    today = date.today().isoformat()
    if _today["date"] != today:
        _today["date"] = today
        _today["count"] = 0
    if _today["count"] >= config.DAILY_CALL_LIMIT:
        stats["quota_exhausted"] = True
        raise DailyLimitReached("Daily LLM call limit reached. Try again tomorrow.")
    _today["count"] += 1


def _cache_file(messages: list[BaseMessage], tools: list | None) -> str:
    """Key = model + message CONTENT + tool schemas. Random message ids are ignored on purpose:
    LangChain gives messages a new id every run, which would make every re-run a cache miss."""
    parts = [{"type": m.type, "content": m.content,
              "tool_calls": [[c["name"], c["args"], c["id"]] for c in (getattr(m, "tool_calls", None) or [])],
              "tool_call_id": getattr(m, "tool_call_id", None)} for m in messages]
    schemas = [convert_to_openai_tool(t) for t in tools or []]
    key = json.dumps([config.LLM_MODEL, parts, schemas], sort_keys=True, default=str)
    return os.path.join(config.CACHE_DIR, hashlib.sha256(key.encode()).hexdigest() + ".json")


def invoke(messages: list[BaseMessage], tools: list | None = None, name: str = "llm-call") -> AIMessage:
    """Send a conversation (optionally with tools), get the AI message back. Safe on the free tier."""
    cache_file = _cache_file(messages, tools)
    if os.path.exists(cache_file):
        stats["cache_hits"] += 1
        with open(cache_file, encoding="utf-8") as f:
            return loads(f.read(), allowed_objects="messages")   # only rebuild chat messages, nothing else

    _check_daily_limit()
    runnable = model.bind_tools(tools) if tools else model
    try:
        message = runnable.invoke(messages, config={"run_name": name})
    except ModelRateLimitError as e:
        if "PerDay" in str(e):                       # daily quota is gone: retrying can't help today
            _today["count"] = config.DAILY_CALL_LIMIT
            stats["quota_exhausted"] = True
            raise DailyLimitReached("Gemini free daily quota is used up.") from e
        raise                                        # per-minute limit: RETRY_POLICY waits and retries
    stats["api_calls"] += 1
    if not message.text and not message.tool_calls:
        raise ValueError("Empty answer from the model")

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(dumps(message))
    return message


def ask(prompt: str, name: str = "llm-call") -> str:
    """One prompt in, text out. (Gemini 3 returns content as blocks; .text joins the text parts.)"""
    return invoke([HumanMessage(prompt)], name=name).text


def parse_json(text: str):
    """Get JSON out of a reply, even if wrapped in ```json ... ``` or surrounded by words."""
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("No JSON found in the reply")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]")) + 1
    return json.loads(text[start:end])


def ask_json(prompt: str, name: str = "llm-call"):
    text = ask(prompt, name)
    try:
        return parse_json(text)
    except ValueError:
        log.warning("Reply was not valid JSON, asking once more")
        return parse_json(ask(prompt + "\n\nYour previous reply was not valid JSON. Reply with ONLY the JSON.", name))


def should_retry(error: Exception) -> bool:
    """Used by LangGraph's RetryPolicy: retry per-minute limits and server errors, never the daily quota."""
    if isinstance(error, RETRYABLE):
        stats["retries"] += 1
        log.warning("Gemini busy (%s), LangGraph will retry this node", type(error).__name__)
        return True
    return False       # DailyLimitReached, bad API key, invalid request, our own errors: fail now


# 10s, 20s, 40s between attempts (exponential backoff), max 4 attempts per node
RETRY_POLICY = RetryPolicy(initial_interval=10, backoff_factor=2, max_attempts=4, jitter=False, retry_on=should_retry)


def tracing_config() -> dict:
    """LangGraph run config that sends every node and LLM call to Langfuse (when configured)."""
    if not config.LANGFUSE_ENABLED:
        return {}
    from langfuse.langchain import CallbackHandler
    return {"callbacks": [CallbackHandler()]}


def flush():
    if config.LANGFUSE_ENABLED:
        from langfuse import get_client
        get_client().flush()
