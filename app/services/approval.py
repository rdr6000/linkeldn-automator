import logging
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import PendingActionModel, HistoryModel, JobModel
from app.services.executor import ActionExecutor
from app.services.generator import ContentGenerator

logger = logging.getLogger(__name__)


class ApprovalService:
    """Service to handle pending actions state management, approvals, rejections, filters, regeneration, and execution."""

    def __init__(
        self,
        db_session: Session,
        executor: Optional[ActionExecutor] = None,
        generator: Optional[ContentGenerator] = None
    ):
        self.db = db_session
        self.executor = executor or ActionExecutor()
        self.generator = generator or ContentGenerator()

    def get_actions(
        self,
        job_id: Optional[int] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = "pending"
    ) -> List[PendingActionModel]:
        """Fetch actions with optional filters for job_id, action_type (comment/connect/follow), and status."""
        query = self.db.query(PendingActionModel)
        if status and status != "all":
            query = query.filter(PendingActionModel.status == status)
        if action_type and action_type != "all":
            query = query.filter(PendingActionModel.action_type == action_type)
        if job_id:
            query = query.filter(PendingActionModel.job_id == job_id)
        return query.order_by(PendingActionModel.created_at.desc()).all()

    def get_pending_actions(self, job_id: Optional[int] = None) -> List[PendingActionModel]:
        """Fetch all actions currently marked as pending."""
        return self.get_actions(job_id=job_id, status="pending")

    def approve_action(self, action_id: int, custom_text: Optional[str] = None, send_note: Optional[bool] = None) -> PendingActionModel:
        """Mark an action as approved (and optionally update generated text or note toggle)."""
        action = self.db.query(PendingActionModel).filter(PendingActionModel.id == action_id).first()
        if not action:
            raise ValueError(f"Action with ID {action_id} not found.")
        
        if send_note is False and action.action_type == "connect":
            action.generated_text = None
        elif custom_text is not None:
            action.generated_text = custom_text

        action.status = "approved"
        action.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(action)
        return action

    def update_action_text(self, action_id: int, new_text: str) -> PendingActionModel:
        """Update generated text for an action on-the-fly without altering status."""
        action = self.db.query(PendingActionModel).filter(PendingActionModel.id == action_id).first()
        if not action:
            raise ValueError(f"Action with ID {action_id} not found.")
        action.generated_text = new_text
        action.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(action)
        return action

    def reject_action(self, action_id: int) -> PendingActionModel:
        """Mark an action as rejected."""
        action = self.db.query(PendingActionModel).filter(PendingActionModel.id == action_id).first()
        if not action:
            raise ValueError(f"Action with ID {action_id} not found.")
        action.status = "rejected"
        action.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(action)
        return action

    def approve_all(self, job_id: Optional[int] = None) -> int:
        """Approve all pending actions for a job or globally."""
        query = self.db.query(PendingActionModel).filter(PendingActionModel.status == "pending")
        if job_id:
            query = query.filter(PendingActionModel.job_id == job_id)
        actions = query.all()
        for act in actions:
            act.status = "approved"
            act.updated_at = datetime.utcnow()
        self.db.commit()
        return len(actions)

    async def regenerate_action(self, action_id: int) -> PendingActionModel:
        """Re-generate AI text for a specified action on-the-fly using Gemini."""
        action = self.db.query(PendingActionModel).filter(PendingActionModel.id == action_id).first()
        if not action:
            raise ValueError(f"Action with ID {action_id} not found.")

        if action.action_type == "comment":
            new_text = await self.generator.generate_comment(
                post_text=action.original_text or "",
                author_name=action.target_name or "LinkedIn User"
            )
        else:
            new_text = await self.generator.generate_connection_note(
                person_name=action.target_name or "LinkedIn User",
                headline=action.original_text or ""
            )

        action.generated_text = new_text
        action.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(action)
        return action

    async def execute_action(self, action_id: int) -> Dict[str, Any]:
        """Execute a specific action by ID (must be approved or pending)."""
        action = self.db.query(PendingActionModel).filter(PendingActionModel.id == action_id).first()
        if not action:
            raise ValueError(f"Action with ID {action_id} not found.")

        if action.action_type == "comment":
            res = await self.executor.execute_comment_action(
                target_url=action.target_url,
                comment_text=action.generated_text or ""
            )
        elif action.action_type in ["connect", "follow"]:
            res = await self.executor.execute_connect_action(
                target_url=action.target_url,
                note=action.generated_text
            )
        else:
            res = {"success": False, "error": f"Unknown action type: {action.action_type}"}

        status_str = "executed" if res.get("success") else "failed"
        action.status = status_str
        action.result_details = json.dumps(res)
        action.updated_at = datetime.utcnow()

        history_entry = HistoryModel(
            action_type=action.action_type,
            target_url=action.target_url,
            target_name=action.target_name,
            status="success" if res.get("success") else "failed",
            details=json.dumps(res),
            timestamp=datetime.utcnow()
        )
        self.db.add(history_entry)
        self.db.commit()
        self.db.refresh(action)
        return res
