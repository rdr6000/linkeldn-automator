from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from app.database import get_db
from app.models import JobModel, PendingActionModel, HistoryModel
from app.config import settings

router = APIRouter(prefix="", tags=["Dashboard"])

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    """Render main Dashboard web UI."""
    total_jobs = db.query(JobModel).count()
    pending_count = db.query(PendingActionModel).filter(PendingActionModel.status == "pending").count()
    executed_count = db.query(HistoryModel).filter(HistoryModel.status == "success").count()
    recent_jobs = db.query(JobModel).order_by(JobModel.id.desc()).limit(5).all()
    recent_history = db.query(HistoryModel).order_by(HistoryModel.id.desc()).limit(10).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total_jobs": total_jobs,
            "pending_count": pending_count,
            "executed_count": executed_count,
            "recent_jobs": recent_jobs,
            "recent_history": recent_history,
            "mode": settings.MODE,
            "mcp_url": settings.MCP_URL,
        }
    )


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """API endpoint for dashboard counters and status."""
    return {
        "total_jobs": db.query(JobModel).count(),
        "pending_actions": db.query(PendingActionModel).filter(PendingActionModel.status == "pending").count(),
        "executed_actions": db.query(HistoryModel).filter(HistoryModel.status == "success").count(),
        "failed_actions": db.query(HistoryModel).filter(HistoryModel.status == "failed").count(),
        "mode": settings.MODE,
        "mcp_url": settings.MCP_URL,
    }
