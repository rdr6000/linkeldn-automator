import asyncio
import json
from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List
from app.database import get_db
from app.models import JobModel, JobSchema, JobRunRequestSchema
from app.services.job_runner import JobRunner
from app.config import settings

router = APIRouter(prefix="", tags=["Jobs"])

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request, db: Session = Depends(get_db)):
    """Render Jobs List Web UI."""
    jobs = db.query(JobModel).order_by(JobModel.id.desc()).all()
    return templates.TemplateResponse(request=request, name="jobs.html", context={"jobs": jobs, "mode": settings.MODE})


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail_page(request: Request, job_id: int, db: Session = Depends(get_db)):
    """Render Job Detail Web UI."""
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(request=request, name="job_detail.html", context={"job": job})


@router.get("/api/jobs", response_model=List[JobSchema])
async def list_jobs(db: Session = Depends(get_db)):
    """API endpoint to get list of jobs."""
    return db.query(JobModel).order_by(JobModel.id.desc()).all()


@router.get("/api/jobs/{job_id}", response_model=JobSchema)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """API endpoint to get job details."""
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/jobs/{job_id}/stream-logs")
async def stream_job_logs(job_id: int, db: Session = Depends(get_db)):
    """Server-Sent Events (SSE) stream endpoint for zero-latency live logs and progress percentage updates."""
    async def event_generator():
        last_logs = ""
        last_pct = -1
        last_status = ""

        while True:
            job = db.query(JobModel).filter(JobModel.id == job_id).first()
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            logs = job.logs or ""
            pct = job.progress_pct or 0
            status = job.status or "running"

            if logs != last_logs or pct != last_pct or status != last_status:
                last_logs = logs
                last_pct = pct
                last_status = status
                payload = {
                    "job_id": job.id,
                    "status": status,
                    "progress_pct": pct,
                    "logs": logs,
                    "actions_count": len(job.actions) if job.actions else 0
                }
                yield f"data: {json.dumps(payload)}\n\n"

            if status in ["completed", "failed", "waiting_approval"]:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/jobs/run")
async def trigger_job(
    background_tasks: BackgroundTasks,
    payload: Optional[JobRunRequestSchema] = None,
    mode: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    """Trigger a new automated LinkedIn automation job with selective action controls."""
    req_mode = payload.mode if payload and payload.mode else mode
    chosen_mode = req_mode or settings.MODE
    chosen_actions = payload.actions if payload and payload.actions is not None else settings.enabled_actions

    job = JobModel(status="created", mode=chosen_mode, logs=f"Job created with actions: {chosen_actions}.\n")
    db.add(job)
    db.commit()
    db.refresh(job)

    async def _execute_job(j_id: int, m: str, acts: List[str]):
        runner = JobRunner()
        await runner.run_job(job_id=j_id, mode=m, actions_to_run=acts)

    background_tasks.add_task(_execute_job, job.id, chosen_mode, chosen_actions)

    return {
        "message": f"Job #{job.id} started successfully in {chosen_mode} mode for actions: {chosen_actions}.",
        "job_id": job.id,
        "mode": chosen_mode,
        "actions": chosen_actions,
        "status": "running"
    }
