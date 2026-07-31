import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import JobModel, PendingActionModel, HistoryModel
from app.services.approval import ApprovalService
from app.services.executor import ActionExecutor
from app.gemini_client import GeminiClient
from app.services.generator import ContentGenerator

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.mark.asyncio
async def test_gemini_client_fallback():
    client = GeminiClient(api_key="mock_key_for_development")
    comment = await client.generate_comment("Post body", "John", "Friendly")
    assert "John" in comment

    note = await client.generate_connection_note("Sarah", "VP Tech", "Warm")
    assert "Sarah" in note

@pytest.mark.asyncio
async def test_approval_service_flow(db_session):
    job = JobModel(status="running", mode="approval")
    db_session.add(job)
    db_session.commit()

    action = PendingActionModel(
        job_id=job.id,
        action_type="comment",
        target_url="https://linkedin.com/posts/test",
        target_name="Test Author",
        generated_text="Initial comment",
        status="pending"
    )
    db_session.add(action)
    db_session.commit()

    svc = ApprovalService(db_session)
    pending = svc.get_pending_actions()
    assert len(pending) == 1

    # Test approval
    approved_act = svc.approve_action(action.id, custom_text="Edited comment")
    assert approved_act.status == "approved"
    assert approved_act.generated_text == "Edited comment"

@pytest.mark.asyncio
async def test_approval_service_update_action_text(db_session):
    job = JobModel(status="running", mode="approval")
    db_session.add(job)
    db_session.commit()

    action = PendingActionModel(
        job_id=job.id,
        action_type="comment",
        target_url="https://linkedin.com/posts/test2",
        target_name="Test Author 2",
        generated_text="Original AI comment",
        status="pending"
    )
    db_session.add(action)
    db_session.commit()

    svc = ApprovalService(db_session)
    updated_act = svc.update_action_text(action.id, new_text="Manually edited comment text")
    assert updated_act.status == "pending"
    assert updated_act.generated_text == "Manually edited comment text"

@pytest.mark.asyncio
async def test_approval_service_connect_send_note_false(db_session):
    job = JobModel(status="running", mode="approval")
    db_session.add(job)
    db_session.commit()

    action = PendingActionModel(
        job_id=job.id,
        action_type="connect",
        target_url="https://linkedin.com/in/testuser",
        target_name="Test User",
        generated_text="Custom AI note draft",
        status="pending"
    )
    db_session.add(action)
    db_session.commit()

    svc = ApprovalService(db_session)
    approved_act = svc.approve_action(action.id, send_note=False)
    assert approved_act.status == "approved"
    assert approved_act.generated_text is None
