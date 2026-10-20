import pytest

from app import db, worker

JOB = {"id": "job-1", "user_id": "demo", "status": "pending", "request": {"goals": "retire"}}


@pytest.fixture
def fake_db(monkeypatch):
    updates = []
    monkeypatch.setattr(db, "get_job", lambda job_id: dict(JOB))
    monkeypatch.setattr(db, "update_job", lambda job_id, **fields: updates.append(fields))
    return updates


def test_completed_job_saves_report_verdict_and_progress(fake_db, monkeypatch):
    def fake_plan(user_id, request, run_config, on_step):
        for step in ["guardrail", "portfolio", "retirement", "reporter", "judge"]:
            on_step(step)
        return {"report": "plan", "facts": {"portfolio": {}}, "revisions": 0,
                "verdict": {"score": 9, "criteria": {}, "reasoning": "good"}}

    monkeypatch.setattr(worker, "run_plan", fake_plan)
    worker.process_job("job-1")
    assert fake_db[-2]["progress"] == ["guardrail", "portfolio", "retirement", "reporter", "judge"]
    assert fake_db[-1]["status"] == "completed" and fake_db[-1]["judge_score"] == 9


def test_blocked_job_is_marked_blocked(fake_db, monkeypatch):
    monkeypatch.setattr(worker, "run_plan", lambda *a, **k: {"blocked": True, "block_reason": "attack"})
    worker.process_job("job-1")
    assert fake_db[-1] == {"status": "blocked", "error": "attack"}


def test_failed_job_is_marked_failed_and_reraised(fake_db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Gemini down")
    monkeypatch.setattr(worker, "run_plan", boom)
    with pytest.raises(RuntimeError):
        worker.process_job("job-1")                     # re-raised so the queue retries
    assert fake_db[-1]["status"] == "failed"


def test_finished_job_is_not_processed_twice(monkeypatch):
    monkeypatch.setattr(db, "get_job", lambda job_id: {**JOB, "status": "completed"})
    monkeypatch.setattr(worker, "run_plan", lambda *a, **k: pytest.fail("must not run again"))
    worker.process_job("job-1")
