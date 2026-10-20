"""All settings in one place. Values come from environment variables (.env locally)."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

# --- Free-tier protection ---
SECONDS_BETWEEN_CALLS = float(os.getenv("SECONDS_BETWEEN_CALLS", "6"))   # 6s = max 10 requests/minute
DAILY_CALL_LIMIT = int(os.getenv("DAILY_CALL_LIMIT", "200"))
CACHE_DIR = os.getenv("CACHE_DIR", str(PROJECT_ROOT / ".cache" / "llm"))

# --- Agents / graph ---
MAX_AGENT_STEPS = 10       # LangGraph recursion limit for one agent (~5 rounds of model + tools)
PASS_SCORE = 7             # judge score needed to skip revision
MAX_REVISIONS = 1          # how often the judge may send a report back

# --- Data ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
PRICE_CACHE_DIR = os.getenv("PRICE_CACHE_DIR", str(PROJECT_ROOT / ".cache" / "prices"))
DEMO_USER = "demo"         # single demo user; a real product takes the user from login (e.g. Clerk JWT)

# --- Queue (empty = local mode: jobs run as background tasks) ---
QSTASH_TOKEN = os.getenv("QSTASH_TOKEN", "")
QSTASH_CURRENT_SIGNING_KEY = os.getenv("QSTASH_CURRENT_SIGNING_KEY", "")
QSTASH_NEXT_SIGNING_KEY = os.getenv("QSTASH_NEXT_SIGNING_KEY", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")

# --- API security ---
API_KEY = os.getenv("API_KEY", "")
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "3"))

# --- Observability (optional) ---
LANGFUSE_ENABLED = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")
