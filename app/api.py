"""Web API. Local mode (no QStash): jobs run as background tasks. Deployed: jobs go through QStash."""
import json
import logging
import secrets
import time
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import config, db, worker

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="FinPilot")
STATIC_DIR = Path(__file__).parent / "static"


class PlanRequest(BaseModel):
    age: int = Field(ge=18, le=90)
    retirement_age: int = Field(ge=30, le=90)
    monthly_contribution: float = Field(ge=0, le=100_000)
    desired_annual_income: float = Field(gt=0, le=1_000_000)
    goals: str = Field(default="", max_length=1000)


def require_api_key(x_api_key: str = Header(default="")):
    if config.API_KEY and not secrets.compare_digest(x_api_key.encode(), config.API_KEY.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


recent_requests: dict[str, list[float]] = {}


def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in recent_requests.get(ip, []) if now - t < 60]
    if len(recent) >= config.REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many plans. Please wait a minute.")
    recent_requests[ip] = recent + [now]


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", status_code=202, dependencies=[Depends(require_api_key), Depends(rate_limit)])
def create_job(req: PlanRequest, background_tasks: BackgroundTasks):
    if req.retirement_age <= req.age:
        raise HTTPException(status_code=422, detail="retirement_age must be greater than age")
    job_id = db.create_job(config.DEMO_USER, req.model_dump())   # user from server config, never from the client
    if config.QSTASH_TOKEN:
        from qstash import QStash
        QStash(config.QSTASH_TOKEN).message.publish_json(
            url=f"{config.PUBLIC_BASE_URL}/worker", body={"job_id": job_id}, retries=3)
    else:
        background_tasks.add_task(worker.process_job, job_id)   # local mode: run right after responding
    return {"job_id": job_id, "status": "pending"}


@app.get("/jobs/latest", dependencies=[Depends(require_api_key)])
def latest_job():
    """The most recent finished plan, so the page opens with real results instead of an empty screen.
    (Declared before /jobs/{job_id}, otherwise "latest" would be read as a job id.)"""
    job = db.get_latest_completed_job(config.DEMO_USER)
    if job is None:
        raise HTTPException(status_code=404, detail="No finished plan yet")
    return job


@app.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def get_job(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/worker")
async def queue_worker(request: Request):
    """Called by QStash only. The signature proves the message really came from our queue."""
    if not config.QSTASH_TOKEN:
        raise HTTPException(status_code=404)
    from qstash import Receiver
    body = (await request.body()).decode()
    receiver = Receiver(current_signing_key=config.QSTASH_CURRENT_SIGNING_KEY,
                        next_signing_key=config.QSTASH_NEXT_SIGNING_KEY)
    try:
        receiver.verify(body=body, signature=request.headers.get("Upstash-Signature", ""),
                        url=f"{config.PUBLIC_BASE_URL}/worker")
    except Exception:
        raise HTTPException(status_code=401, detail="Bad signature")
    worker.process_job(json.loads(body)["job_id"])
    return {"ok": True}
