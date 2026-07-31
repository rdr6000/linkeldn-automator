import asyncio
import json
import logging
import random
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models import JobModel, PendingActionModel, HistoryModel
from app.services.collector import collect_posts_and_people
from app.services.generator import ContentGenerator
from app.services.executor import ActionExecutor
from app.mcp.client import LinkedInMCP

logger = logging.getLogger(__name__)


def is_already_processed(db: Session, target_url: str, action_type: str) -> bool:
    """Check if target_url has already been processed or is pending in DB."""
    hist = db.query(HistoryModel).filter(
        HistoryModel.target_url == target_url,
        HistoryModel.action_type == action_type
    ).first()
    if hist:
        return True

    pending = db.query(PendingActionModel).filter(
        PendingActionModel.target_url == target_url,
        PendingActionModel.action_type == action_type,
        PendingActionModel.status.in_(["pending", "approved", "executed"])
    ).first()
    return pending is not None


def filter_new_items(db: Session, items: List[Dict[str, Any]], action_type: str) -> List[Dict[str, Any]]:
    """Filter out items that have already been processed or are in progress."""
    filtered = []
    for item in items:
        url = item.get("url", "")
        if url and not is_already_processed(db, url, action_type):
            filtered.append(item)
    return filtered


class JobRunner:
    """Orchestrates job lifecycle with fast parallel batch AI generation and real-time progress tracking."""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        generator: Optional[ContentGenerator] = None,
        executor: Optional[ActionExecutor] = None,
        mcp_client: Optional[LinkedInMCP] = None
    ):
        self.db = db_session
        self.generator = generator or ContentGenerator()
        self.executor = executor or ActionExecutor(mcp_client=mcp_client)
        self.mcp_client = mcp_client

    async def run_job(self, job_id: int, mode: Optional[str] = None, actions_to_run: Optional[List[str]] = None) -> JobModel:
        db = self.db or SessionLocal()
        close_db_on_exit = self.db is None

        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            if close_db_on_exit:
                db.close()
            raise ValueError(f"Job with ID {job_id} not found.")

        effective_mode = mode or job.mode or settings.MODE
        active_actions = actions_to_run if actions_to_run is not None else settings.enabled_actions

        job.status = "running"
        job.progress_pct = 5
        job.logs = f"[{datetime.utcnow().strftime('%H:%M:%S')}] Job #{job_id} initiated in '{effective_mode}' mode for actions: {active_actions}.\n"
        db.commit()

        try:
            posts, people = [], []
            
            # 1. Priority Data Collection via MCP
            if "comment" in active_actions or "like" in active_actions:
                job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Priority 1: Fetching feed & search posts via LinkedIn MCP...\n"
                job.progress_pct = 15
                db.commit()

            collected_posts, collected_people = await collect_posts_and_people(mcp_client=self.mcp_client)

            if "comment" in active_actions or "like" in active_actions:
                posts = collected_posts
            if "connect" in active_actions or "follow" in active_actions or "search_people" in active_actions:
                people = collected_people

            # 2. Filter & Limit
            posts = filter_new_items(db, posts, action_type="comment")[:settings.daily_limits.comments]
            people = filter_new_items(db, people, action_type="connect")[:settings.daily_limits.connections]

            job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Priority collection filtered to {len(posts)} new posts & {len(people)} new people.\n"
            job.progress_pct = 30
            db.commit()

            pending_actions: List[PendingActionModel] = []

            # 3. Fast Parallel Batch AI Generation
            if "comment" in active_actions and posts:
                job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Launching fast parallel AI batch generation for {len(posts)} comments...\n"
                job.progress_pct = 45
                db.commit()

                comment_texts = await self.generator.generate_comments_batch(posts, batch_size=5)

                for p, text in zip(posts, comment_texts):
                    act = PendingActionModel(
                        job_id=job_id,
                        action_type="comment",
                        target_url=p.get("url", ""),
                        target_name=p.get("author", "LinkedIn User"),
                        original_text=p.get("text", "")[:1500],
                        generated_text=text,
                        status="pending" if effective_mode == "approval" else "approved"
                    )
                    db.add(act)
                    pending_actions.append(act)

            if "connect" in active_actions and people:
                if settings.generate_custom_connection_notes:
                    job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Generate Custom Notes ENABLED: Generating AI connection notes for {len(people)} targets...\n"
                    job.progress_pct = 60
                    db.commit()

                    note_texts = await self.generator.generate_connection_notes_batch(people, batch_size=5)
                else:
                    job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Generate Custom Notes DISABLED in Settings. Skipping AI note generation.\n"
                    job.progress_pct = 60
                    db.commit()
                    note_texts = [None] * len(people)

                for person, text in zip(people, note_texts):
                    act = PendingActionModel(
                        job_id=job_id,
                        action_type="connect",
                        target_url=person.get("url", ""),
                        target_name=person.get("name", "LinkedIn User"),
                        original_text=person.get("headline", ""),
                        generated_text=text,
                        status="pending" if effective_mode == "approval" else "approved"
                    )
                    db.add(act)
                    pending_actions.append(act)

            db.commit()

            # 4. Approval vs Autonomous Execution
            if effective_mode == "approval":
                job.status = "waiting_approval"
                job.progress_pct = 100
                job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Fast batch generation complete! {len(pending_actions)} actions awaiting approval in UI.\n"
                db.commit()
            else:
                job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Autonomous mode: executing {len(pending_actions)} actions with human pacing...\n"
                job.progress_pct = 70
                db.commit()

                total = len(pending_actions)
                for idx, act in enumerate(pending_actions, start=1):
                    db.refresh(act)
                    if act.action_type == "comment":
                        res = await self.executor.execute_comment_action(act.target_url, act.generated_text or "")
                    else:
                        res = await self.executor.execute_connect_action(act.target_url, act.generated_text)

                    status_str = "executed" if res.get("success") else "failed"
                    act.status = status_str
                    act.result_details = json.dumps(res)

                    hist = HistoryModel(
                        action_type=act.action_type,
                        target_url=act.target_url,
                        target_name=act.target_name,
                        status="success" if res.get("success") else "failed",
                        details=json.dumps(res),
                        timestamp=datetime.utcnow()
                    )
                    db.add(hist)
                    
                    pct = 70 + int((idx / total) * 30)
                    job.progress_pct = min(pct, 99)
                    job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Executed {act.action_type} for '{act.target_name}' ({idx}/{total}).\n"
                    db.commit()

                    if idx < total:
                        delay = random.uniform(6.0, 12.0)
                        await asyncio.sleep(delay)

                job.status = "completed"
                job.progress_pct = 100
                job.completed_at = datetime.utcnow()
                job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] Job execution completed 100% successfully.\n"
                db.commit()

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            job.status = "failed"
            job.logs += f"[{datetime.utcnow().strftime('%H:%M:%S')}] ERROR: {str(e)}\n"
            db.commit()

        finally:
            if close_db_on_exit:
                db.close()

        return job
