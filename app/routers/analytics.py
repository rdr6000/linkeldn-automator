from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path
from datetime import datetime, timedelta
from app.database import get_db
from app.models import HistoryModel, PendingActionModel, JobModel
from app.config import settings

router = APIRouter(prefix="", tags=["Analytics"])

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, db: Session = Depends(get_db)):
    """Render Analytics & Engagement Conversion Dashboard."""
    history = db.query(HistoryModel).order_by(HistoryModel.timestamp.desc()).all()
    
    total_exec = len(history)
    success_count = sum(1 for h in history if h.status == "success")
    failed_count = sum(1 for h in history if h.status == "failed")
    success_rate = round((success_count / total_exec * 100), 1) if total_exec > 0 else 100.0

    comments_count = sum(1 for h in history if h.action_type == "comment")
    connects_count = sum(1 for h in history if h.action_type == "connect")
    follows_count = sum(1 for h in history if h.action_type == "follow")

    pending_approvals = db.query(PendingActionModel).filter(PendingActionModel.status == "pending").count()
    completed_jobs = db.query(JobModel).filter(JobModel.status == "completed").count()

    # Calculate daily execution stats for last 7 days
    daily_stats = []
    now = datetime.utcnow()
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        day_start = datetime.combine(day_date, datetime.min.time())
        day_end = datetime.combine(day_date, datetime.max.time())
        count = db.query(HistoryModel).filter(HistoryModel.timestamp >= day_start, HistoryModel.timestamp <= day_end).count()
        daily_stats.append({
            "date": day_date.strftime("%b %d"),
            "count": count
        })

    # Recent target engagements
    recent_targets = history[:10]

    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "settings": settings,
            "total_exec": total_exec,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_rate,
            "comments_count": comments_count,
            "connects_count": connects_count,
            "follows_count": follows_count,
            "pending_approvals": pending_approvals,
            "completed_jobs": completed_jobs,
            "daily_stats": daily_stats,
            "recent_targets": recent_targets
        }
    )


@router.get("/api/analytics")
async def get_analytics_api(db: Session = Depends(get_db)):
    """API endpoint returning raw analytics metrics."""
    history = db.query(HistoryModel).all()
    total_exec = len(history)
    success_count = sum(1 for h in history if h.status == "success")
    failed_count = sum(1 for h in history if h.status == "failed")
    return {
        "total_executions": total_exec,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": round((success_count / total_exec * 100), 1) if total_exec > 0 else 100.0,
        "comments": sum(1 for h in history if h.action_type == "comment"),
        "connections": sum(1 for h in history if h.action_type == "connect"),
        "follows": sum(1 for h in history if h.action_type == "follow")
    }
