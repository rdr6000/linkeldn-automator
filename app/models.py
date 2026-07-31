from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, ConfigDict
from app.database import Base


# ============================================================================
# SQLAlchemy ORM Models
# ============================================================================

class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    status = Column(String(50), default="running", index=True)  # running, waiting_approval, completed, failed
    mode = Column(String(20), default="approval")                # approval, autonomous
    progress_pct = Column(Integer, default=0)
    logs = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    actions = relationship("PendingActionModel", back_populates="job", cascade="all, delete-orphan")


class PendingActionModel(Base):
    __tablename__ = "pending_actions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    action_type = Column(String(50), index=True)   # comment, connect
    target_url = Column(Text, nullable=False)
    target_name = Column(String(255), nullable=True)
    original_text = Column(Text, nullable=True)
    generated_text = Column(Text, nullable=True)
    status = Column(String(50), default="pending", index=True)  # pending, approved, rejected, executed, failed
    result_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("JobModel", back_populates="actions")


class HistoryModel(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    action_type = Column(String(50), index=True)   # comment, connect
    target_url = Column(Text, nullable=False, index=True)
    target_name = Column(String(255), nullable=True)
    status = Column(String(50), default="success")  # success, failed
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class PendingActionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    job_id: int
    action_type: str
    target_url: str
    target_name: Optional[str] = None
    original_text: Optional[str] = None
    generated_text: Optional[str] = None
    status: str = "pending"
    result_details: Optional[str] = None


class JobSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    status: str
    mode: str
    progress_pct: int = 0
    logs: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actions: List[PendingActionSchema] = []


class ActionUpdateSchema(BaseModel):
    generated_text: Optional[str] = None
    send_note: Optional[bool] = True
    status: Optional[str] = None  # approved, rejected


class SettingsUpdateSchema(BaseModel):
    mode: Optional[str] = None
    active_profile: Optional[str] = None
    headless: Optional[bool] = None
    ai_provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_model: Optional[str] = None
    keywords: Optional[List[str]] = None
    recency: Optional[str] = None
    post_sort_by: Optional[str] = None
    post_content_type: Optional[str] = None
    people_network_degree: Optional[str] = None
    people_title_filter: Optional[str] = None
    people_location_filter: Optional[str] = None
    feed_sort_by: Optional[str] = None
    generate_custom_connection_notes: Optional[bool] = None
    send_custom_connection_notes: Optional[bool] = None
    comment_style: Optional[str] = None
    connection_note_style: Optional[str] = None
    custom_instructions: Optional[str] = None
    user_persona: Optional[str] = None
    enabled_actions: Optional[List[str]] = None
    max_feed_posts: Optional[int] = None
    max_posts_per_keyword: Optional[int] = None
    max_people_per_keyword: Optional[int] = None
    max_comments: Optional[int] = None
    max_connections: Optional[int] = None


class JobRunRequestSchema(BaseModel):
    mode: Optional[str] = None
    actions: Optional[List[str]] = None
