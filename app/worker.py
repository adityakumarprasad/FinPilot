"""Processes one planning job by running the LangGraph workflow. Safe to call twice (idempotent)."""
import logging

from app import config, db, llm
from app.graph import run_plan

log = logging.getLogger(__name__)


def process_job(job_id: str):
    job = db.get_job(job_id)
    if job is None or job["status"] in ("completed", "blocked"):
        return                                         # already done: a duplicate queue delivery is harmless
    db.update_job(job_id, status="running", progress=[])

    steps = []

    def save_progress(node_name: str):                 # called by the graph after every finished node
        steps.append(node_name)
        db.update_job(job_id, progress=steps)

    try:
        state = run_plan(job["user_id"], job["request"], llm.tracing_config(), on_step=save_progress)
    except Exception as e:
        log.exception("Job %s failed", job_id)
        db.update_job(job_id, status="failed", error=f"{type(e).__name__}: {e}"[:500])
        raise                                          # non-2xx -> the queue retries
    finally:
        llm.flush()

    if state.get("blocked"):
        db.update_job(job_id, status="blocked", error=state["block_reason"])
        return
    verdict = state["verdict"]
    db.update_job(job_id, status="completed", report=state["report"], facts=state["facts"],
                  judge_score=verdict["score"], judge_criteria=verdict["criteria"],
                  judge_notes=verdict["reasoning"], revisions=state.get("revisions", 0))
    if config.LANGFUSE_ENABLED:
        from langfuse import get_client
        get_client().score_current_trace(name="judge_score", value=verdict["score"],
                                         metadata={"revisions": state.get("revisions", 0),
                                                   "prompt_version": config.PROMPT_VERSION})


# One Langfuse trace per job. The graph's CallbackHandler (from tracing_config) nests all nodes and
# LLM calls inside it, and score_current_trace above attaches the judge score to it.
if config.LANGFUSE_ENABLED:
    from langfuse import observe
    process_job = observe(name="planning-job")(process_job)
