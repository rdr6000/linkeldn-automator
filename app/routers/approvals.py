from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List
from app.database import get_db
from app.config import settings
from app.models import PendingActionModel, PendingActionSchema, ActionUpdateSchema
from app.services.approval import ApprovalService

router = APIRouter(prefix="", tags=["Approvals"])

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/approvals", response_class=HTMLResponse)
async def approvals_page(
    request: Request,
    action_type: Optional[str] = Query("all"),
    status: Optional[str] = Query("pending"),
    db: Session = Depends(get_db)
):
    """Render Approvals Review Web UI with dynamic filters."""
    svc = ApprovalService(db)
    actions = svc.get_actions(action_type=action_type, status=status)
    return templates.TemplateResponse(
        request=request,
        name="approvals.html",
        context={
            "actions": actions,
            "settings": settings,
            "current_type": action_type or "all",
            "current_status": status or "pending"
        }
    )


@router.get("/api/approvals", response_model=List[PendingActionSchema])
async def list_actions_api(
    job_id: Optional[int] = None,
    action_type: Optional[str] = Query("all"),
    status: Optional[str] = Query("pending"),
    db: Session = Depends(get_db)
):
    """API endpoint to get list of actions with optional filters."""
    svc = ApprovalService(db)
    return svc.get_actions(job_id=job_id, action_type=action_type, status=status)


@router.post("/api/approvals/{action_id}/approve", response_model=PendingActionSchema)
async def approve_action(action_id: int, payload: Optional[ActionUpdateSchema] = None, db: Session = Depends(get_db)):
    """Approve a single action (and optionally update text / send_note flag)."""
    svc = ApprovalService(db)
    try:
        custom_text = payload.generated_text if payload else None
        send_note = payload.send_note if payload else True
        return svc.approve_action(action_id=action_id, custom_text=custom_text, send_note=send_note)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/approvals/{action_id}/reject", response_model=PendingActionSchema)
async def reject_action(action_id: int, db: Session = Depends(get_db)):
    """Reject a single action."""
    svc = ApprovalService(db)
    try:
        return svc.reject_action(action_id=action_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/approvals/{action_id}/regenerate", response_model=PendingActionSchema)
async def regenerate_action(action_id: int, db: Session = Depends(get_db)):
    """Re-generate AI text for an action on-the-fly using Gemini."""
    svc = ApprovalService(db)
    try:
        return await svc.regenerate_action(action_id=action_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/approvals/{action_id}/update-text", response_model=PendingActionSchema)
async def update_action_text_api(action_id: int, payload: ActionUpdateSchema, db: Session = Depends(get_db)):
    """Save custom edited text for an action on-the-fly."""
    svc = ApprovalService(db)
    try:
        new_text = payload.generated_text or ""
        return svc.update_action_text(action_id=action_id, new_text=new_text)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/approvals/{action_id}/execute")
async def execute_approved_action(action_id: int, db: Session = Depends(get_db)):
    """Execute an approved action immediately."""
    svc = ApprovalService(db)
    try:
        result = await svc.execute_action(action_id)
        return {"action_id": action_id, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/approvals/approve-all")
async def approve_all_pending(job_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Approve all pending actions."""
    svc = ApprovalService(db)
    count = svc.approve_all(job_id=job_id)
    return {"message": f"Successfully approved {count} actions.", "approved_count": count}
