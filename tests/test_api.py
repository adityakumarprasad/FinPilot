from fastapi.testclient import TestClient

from app import api, config, db, worker

client = TestClient(api.app)
VALID = {"age": 30, "retirement_age": 60, "monthly_contribution": 500, "desired_annual_income": 40000, "goals": "retire"}


def test_missing_api_key_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret")
    assert client.post("/jobs", json=VALID).status_code == 401


def test_retirement_age_must_be_after_age(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(api, "recent_requests", {})
    assert client.post("/jobs", json={**VALID, "retirement_age": 30}).status_code == 422


def test_local_mode_runs_job_in_background(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(config, "QSTASH_TOKEN", "")
    monkeypatch.setattr(api, "recent_requests", {})
    monkeypatch.setattr(db, "create_job", lambda user_id, request: "job-1")
    processed = []
    monkeypatch.setattr(worker, "process_job", lambda job_id: processed.append(job_id))
    assert client.post("/jobs", json=VALID).status_code == 202 and processed == ["job-1"]


def test_rate_limit_blocks_too_many_plans(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(config, "QSTASH_TOKEN", "")
    monkeypatch.setattr(config, "REQUESTS_PER_MINUTE", 2)
    monkeypatch.setattr(api, "recent_requests", {})
    monkeypatch.setattr(db, "create_job", lambda user_id, request: "job-1")
    monkeypatch.setattr(worker, "process_job", lambda job_id: None)
    codes = [client.post("/jobs", json=VALID).status_code for _ in range(3)]
    assert codes == [202, 202, 429]


def test_worker_endpoint_is_closed_without_queue(monkeypatch):
    monkeypatch.setattr(config, "QSTASH_TOKEN", "")
    assert client.post("/worker", json={"job_id": "x"}).status_code == 404


def test_home_page_is_served_and_sanitizes_report():
    page = client.get("/").text
    assert "FinPilot" in page and "DOMPurify.sanitize" in page


def test_latest_plan_is_returned(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(db, "get_latest_completed_job", lambda user_id: {"id": "job-9", "status": "completed"})
    assert client.get("/jobs/latest").json()["id"] == "job-9"      # not mistaken for a job id


def test_no_latest_plan_gives_404(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(db, "get_latest_completed_job", lambda user_id: None)
    assert client.get("/jobs/latest").status_code == 404
