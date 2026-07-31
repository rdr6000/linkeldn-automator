import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FeedSettings(BaseModel):
    enabled: bool = True
    sort_by: str = "recent"  # "recent" or "top"
    max_feed_comments: int = 5
    max_feed_likes: int = 5


class SearchSettings(BaseModel):
    max_posts_per_keyword: int = 3
    max_people_per_keyword: int = 3
    sort_by: str = "relevance"       # "relevance" or "date_posted"
    content_type: str = "all"        # "all", "videos", "photos", "documents"
    network_degree: str = "2nd"      # "1st", "2nd", "3rd", "all"
    title_filter: str = ""           # e.g. "Founder", "Software Engineer"
    location_filter: str = ""        # e.g. "United States", "San Francisco"


class DailyLimits(BaseModel):
    max_feed_posts: int = 50
    comments: int = 10
    connections: int = 10


class AppConfig(BaseSettings):
    """Application settings combining env vars and config.yaml with full persistence support and OpenAI/Gemini support."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GEMINI_API_KEY: str = Field(default="", validation_alias="GEMINI_API_KEY")
    OPENAI_API_KEY: str = Field(default="", validation_alias="OPENAI_API_KEY")
    MCP_URL: str = Field(default="http://localhost:8001/mcp", validation_alias="MCP_URL")
    HEADLESS: bool = Field(default=True, validation_alias="HEADLESS")
    PLAYWRIGHT_STORAGE: str = Field(default="data/cookies.json", validation_alias="PLAYWRIGHT_STORAGE")
    DATABASE_URL: str = Field(default="sqlite:///./data/history.db", validation_alias="DATABASE_URL")
    MODE: str = Field(default="approval", validation_alias="MODE")

    active_profile: str = "default"
    available_profiles: List[str] = Field(default_factory=lambda: ["default", "work_profile", "personal_profile"])

    ai_provider: str = "gemini"  # "gemini" or "openai"
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"

    feed: FeedSettings = Field(default_factory=FeedSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    recency: str = "past-week"
    keywords: List[str] = Field(default_factory=lambda: ["AI automation", "Software Engineering"])
    generate_custom_connection_notes: bool = True
    send_custom_connection_notes: bool = True
    comment_style: str = "Specific, insightful, highly relevant to post details, peer-to-peer conversational, 1-3 sentences"
    connection_note_style: str = "Warm, specific, referencing target headline or domain focus, under 180 characters"
    custom_instructions: str = "NO generic AI slop ('Great post!', 'Thanks for sharing!', 'Spot on!', 'In today's fast-paced world'). Quote or reference specific facts/ideas from the post. Sound like an authentic human peer having a real conversation."
    user_persona: str = ""
    enabled_actions: List[str] = Field(default_factory=lambda: ["comment", "connect", "follow"])
    daily_limits: DailyLimits = Field(default_factory=DailyLimits)

    @classmethod
    def load(cls, config_path: str = "config.yaml") -> "AppConfig":
        """Load configuration from config.yaml or config.default.yaml if present, auto-generating config.yaml on first launch."""
        yaml_data: Dict[str, Any] = {}
        path = Path(config_path)
        default_path = Path("config.default.yaml")

        target_file = None
        if path.exists():
            target_file = path
        elif default_path.exists():
            target_file = default_path

        if target_file:
            with open(target_file, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}

        # Handle nested models if present in yaml
        if "feed" in yaml_data and isinstance(yaml_data["feed"], dict):
            yaml_data["feed"] = FeedSettings(**yaml_data["feed"])
        if "search" in yaml_data and isinstance(yaml_data["search"], dict):
            yaml_data["search"] = SearchSettings(**yaml_data["search"])
        if "daily_limits" in yaml_data and isinstance(yaml_data["daily_limits"], dict):
            yaml_data["daily_limits"] = DailyLimits(**yaml_data["daily_limits"])

        # Override with environment variables if present
        env_mcp = os.getenv("MCP_URL")
        if env_mcp:
            yaml_data["MCP_URL"] = env_mcp
        env_gemini = os.getenv("GEMINI_API_KEY")
        if env_gemini:
            yaml_data["GEMINI_API_KEY"] = env_gemini
        env_openai = os.getenv("OPENAI_API_KEY")
        if env_openai:
            yaml_data["OPENAI_API_KEY"] = env_openai
        env_mode = os.getenv("MODE")
        if env_mode:
            yaml_data["MODE"] = env_mode
        env_headless = os.getenv("HEADLESS")
        if env_headless is not None:
            yaml_data["HEADLESS"] = env_headless.lower() in ("true", "1", "yes")

        config_obj = cls(**yaml_data)
        if not path.exists():
            try:
                config_obj.save_to_yaml(config_path)
            except Exception:
                pass
        return config_obj

    def save_to_yaml(self, config_path: str = "config.yaml") -> None:
        """Persist current settings configuration permanently back to config.yaml."""
        data = {
            "mcp_url": self.MCP_URL,
            "headless": self.HEADLESS,
            "playwright_storage": self.PLAYWRIGHT_STORAGE,
            "database_url": self.DATABASE_URL,
            "active_profile": self.active_profile,
            "available_profiles": self.available_profiles,
            "ai_provider": self.ai_provider,
            "gemini_model": self.gemini_model,
            "openai_model": self.openai_model,
            "recency": self.recency,
            "keywords": self.keywords,
            "generate_custom_connection_notes": self.generate_custom_connection_notes,
            "send_custom_connection_notes": self.send_custom_connection_notes,
            "comment_style": self.comment_style,
            "connection_note_style": self.connection_note_style,
            "custom_instructions": self.custom_instructions,
            "user_persona": self.user_persona,
            "enabled_actions": self.enabled_actions,
            "feed": {
                "enabled": self.feed.enabled,
                "sort_by": self.feed.sort_by,
                "max_feed_comments": self.feed.max_feed_comments,
                "max_feed_likes": self.feed.max_feed_likes
            },
            "search": {
                "max_posts_per_keyword": self.search.max_posts_per_keyword,
                "max_people_per_keyword": self.search.max_people_per_keyword,
                "sort_by": self.search.sort_by,
                "content_type": self.search.content_type,
                "network_degree": self.search.network_degree,
                "title_filter": self.search.title_filter,
                "location_filter": self.search.location_filter
            },
            "daily_limits": {
                "max_feed_posts": self.daily_limits.max_feed_posts,
                "comments": self.daily_limits.comments,
                "connections": self.daily_limits.connections,
            }
        }
        path = Path(config_path)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


settings = AppConfig.load()
