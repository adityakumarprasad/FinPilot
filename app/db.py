"""All database access. Values ALWAYS go through %s parameters (never f-strings) to prevent SQL injection."""
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app import config

JOB_FIELDS = {"status", "progress", "report", "facts", "judge_score", "judge_criteria", "judge_notes",
              "revisions", "error"}


def conn():
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)


def get_holdings(user_id: str) -> list[dict]:
    with conn() as c:
        return c.execute("SELECT symbol, name, quantity, avg_cost, asset_class FROM holdings WHERE user_id = %s",
                         (user_id,)).fetchall()


def create_job(user_id: str, request: dict) -> str:
    with conn() as c:
        row = c.execute("INSERT INTO jobs (user_id, request) VALUES (%s, %s) RETURNING id",
                        (user_id, Jsonb(request))).fetchone()
    return str(row["id"])


def get_job(job_id: str) -> dict | None:
    with conn() as c:
        return c.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()


def get_latest_completed_job(user_id: str) -> dict | None:
    with conn() as c:
        return c.execute("SELECT * FROM jobs WHERE user_id = %s AND status = 'completed' "
                         "ORDER BY updated_at DESC LIMIT 1", (user_id,)).fetchone()


def update_job(job_id: str, **fields):
    unknown = set(fields) - JOB_FIELDS
    if unknown:                                   # column names can't be parameters, so we allow-list them
        raise ValueError(f"Unknown job fields: {unknown}")
    values = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in fields.values()]
    sets = ", ".join(f"{name} = %s" for name in fields) + ", updated_at = now()"
    with conn() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id = %s", (*values, job_id))
