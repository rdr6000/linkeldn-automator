import json
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models import SettingsUpdateSchema, PendingActionModel, JobModel, HistoryModel
from app.mcp.client import LinkedInMCP
from app.mcp.tools import MCPTools
from app.services.generator import ContentGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Settings"])

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render Settings configuration Web UI."""
    return templates.TemplateResponse(request=request, name="settings.html", context={"settings": settings})


@router.get("/api/settings")
async def get_settings():
    """API endpoint to get current active settings."""
    return {
        "mode": settings.MODE,
        "active_profile": settings.active_profile,
        "available_profiles": settings.available_profiles,
        "headless": settings.HEADLESS,
        "mcp_url": settings.MCP_URL,
        "ai_provider": settings.ai_provider,
        "gemini_model": settings.gemini_model,
        "openai_model": settings.openai_model,
        "keywords": settings.keywords,
        "recency": settings.recency,
        "post_sort_by": settings.search.sort_by,
        "post_content_type": settings.search.content_type,
        "people_network_degree": settings.search.network_degree,
        "people_title_filter": settings.search.title_filter,
        "people_location_filter": settings.search.location_filter,
        "feed_sort_by": settings.feed.sort_by,
        "generate_custom_connection_notes": settings.generate_custom_connection_notes,
        "send_custom_connection_notes": settings.send_custom_connection_notes,
        "comment_style": settings.comment_style,
        "connection_note_style": settings.connection_note_style,
        "custom_instructions": settings.custom_instructions,
        "user_persona": settings.user_persona,
        "enabled_actions": settings.enabled_actions,
        "daily_limits": {
            "max_feed_posts": settings.daily_limits.max_feed_posts,
            "max_posts_per_keyword": settings.search.max_posts_per_keyword,
            "max_people_per_keyword": settings.search.max_people_per_keyword,
            "comments": settings.daily_limits.comments,
            "connections": settings.daily_limits.connections
        }
    }


@router.post("/api/settings")
async def update_settings(payload: SettingsUpdateSchema):
    """API endpoint to update operational settings dynamically and save to config.yaml."""
    if payload.mode:
        settings.MODE = payload.mode
    if payload.active_profile:
        settings.active_profile = payload.active_profile
        if payload.active_profile not in settings.available_profiles:
            settings.available_profiles.append(payload.active_profile)
    if payload.headless is not None:
        settings.HEADLESS = payload.headless
    if payload.ai_provider:
        settings.ai_provider = payload.ai_provider
    if payload.openai_api_key is not None:
        settings.OPENAI_API_KEY = payload.openai_api_key
    if payload.gemini_model:
        settings.gemini_model = payload.gemini_model
    if payload.openai_model:
        settings.openai_model = payload.openai_model
    if payload.keywords:
        settings.keywords = payload.keywords
    if payload.recency:
        settings.recency = payload.recency
    if payload.post_sort_by:
        settings.search.sort_by = payload.post_sort_by
    if payload.post_content_type:
        settings.search.content_type = payload.post_content_type
    if payload.people_network_degree:
        settings.search.network_degree = payload.people_network_degree
    if payload.people_title_filter is not None:
        settings.search.title_filter = payload.people_title_filter
    if payload.people_location_filter is not None:
        settings.search.location_filter = payload.people_location_filter
    if payload.feed_sort_by:
        settings.feed.sort_by = payload.feed_sort_by
    if payload.generate_custom_connection_notes is not None:
        settings.generate_custom_connection_notes = payload.generate_custom_connection_notes
    if payload.send_custom_connection_notes is not None:
        settings.send_custom_connection_notes = payload.send_custom_connection_notes
    if payload.comment_style:
        settings.comment_style = payload.comment_style
    if payload.connection_note_style:
        settings.connection_note_style = payload.connection_note_style
    if payload.custom_instructions is not None:
        settings.custom_instructions = payload.custom_instructions
    if payload.user_persona is not None:
        settings.user_persona = payload.user_persona
    if payload.enabled_actions is not None:
        settings.enabled_actions = payload.enabled_actions
    if payload.max_feed_posts is not None:
        settings.daily_limits.max_feed_posts = payload.max_feed_posts
    if payload.max_posts_per_keyword is not None:
        settings.search.max_posts_per_keyword = payload.max_posts_per_keyword
    if payload.max_people_per_keyword is not None:
        settings.search.max_people_per_keyword = payload.max_people_per_keyword
    if payload.max_comments is not None:
        settings.daily_limits.comments = payload.max_comments
    if payload.max_connections is not None:
        settings.daily_limits.connections = payload.max_connections

    # Save to config.yaml so settings persist across restarts
    settings.save_to_yaml()

    return {
        "message": "Settings updated and saved permanently.",
        "settings": await get_settings()
    }


@router.post("/api/settings/generate-my-bio")
async def generate_my_bio():
    """Use MCP to fetch user profile data and active AI provider (Gemini or OpenAI) to synthesize persona description."""
    logger.info("Fetching logged-in user profile via MCP...")
    mcp = LinkedInMCP()
    tools = MCPTools(mcp)

    try:
        profile_raw = await tools.get_my_profile(sections=["experience", "skills", "about"])
        profile_str = json.dumps(profile_raw) if isinstance(profile_raw, (dict, list)) else str(profile_raw)
    except Exception as e:
        logger.error(f"Error fetching profile via MCP: {e}")
        profile_str = "Software developer experienced in AI automation, web applications, and Python systems."

    generator = ContentGenerator()
    logger.info(f"Synthesizing user persona description via active provider ({settings.ai_provider})...")
    persona = await generator.synthesize_user_persona(profile_str)

    settings.user_persona = persona
    settings.save_to_yaml()

    return {
        "message": f"User persona successfully generated from LinkedIn profile via {settings.ai_provider.upper()} and saved to settings!",
        "user_persona": persona
    }


@router.post("/api/admin/clear-all")
async def clear_all_data(db: Session = Depends(get_db)):
    """Clear all pending actions, jobs, and execution history logs from database."""
    try:
        db.query(PendingActionModel).delete()
        db.query(JobModel).delete()
        db.query(HistoryModel).delete()
        db.commit()
        logger.info("Successfully cleared all database logs, jobs, and pending actions.")
        return {"message": "All logs, pending actions, jobs, and execution history cleared successfully!"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing database records: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {e}")
