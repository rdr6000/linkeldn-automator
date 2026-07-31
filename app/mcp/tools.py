from typing import Any, List, Optional, Dict
from app.mcp.client import LinkedInMCP


def extract_username(url_or_username: str) -> str:
    """Extract LinkedIn username slug from profile URL or return raw username."""
    if not url_or_username:
        return ""
    clean = url_or_username.strip().rstrip('/')
    if "linkedin.com/in/" in clean:
        clean = clean.split("linkedin.com/in/")[-1]
    elif "linkedin.com/pub/" in clean:
        clean = clean.split("linkedin.com/pub/")[-1]
    return clean.split('/')[0].split('?')[0].split('#')[0]


class MCPTools:
    """Typed helper methods for calling stickerdaniel/linkedin-mcp-server tools."""

    def __init__(self, client: LinkedInMCP):
        self.c = client

    async def get_feed(self, limit: int = 50) -> Any:
        """Fetch home feed posts via MCP."""
        num_posts = max(1, min(limit, 50))
        return await self.c.call("get_feed", {"num_posts": num_posts})

    async def search_posts(self, keywords: str, recency: Optional[str] = None, sort_by: Optional[str] = None, content_type: Optional[str] = None) -> Any:
        """Search LinkedIn posts by keyword, recency, sort order, and content type via MCP."""
        r = recency or settings.recency
        date_posted = "past-week"
        if r in ["past-24h", "past_24_hours", "past_24h"]:
            date_posted = "past-24h"
        elif r in ["past-month", "past_month"]:
            date_posted = "past-month"

        args = {
            "keywords": keywords,
            "date_posted": date_posted
        }
        if sort_by:
            args["sort_by"] = sort_by
        if content_type and content_type != "all":
            args["content_type"] = content_type

        return await self.c.call("search_posts", args)

    async def search_people(self, keywords: str, connection_degree: Optional[str] = None, title: Optional[str] = None, location: Optional[str] = None) -> Any:
        """Search LinkedIn people profiles by keyword, network degree, job title, and location via MCP."""
        deg = connection_degree or settings.search.network_degree
        network = ["S"]
        if deg in ["1st", "F"]:
            network = ["F"]
        elif deg in ["3rd", "O"]:
            network = ["O"]
        elif deg in ["all", "A"]:
            network = ["F", "S", "O"]

        args = {
            "keywords": keywords,
            "network": network
        }
        if title:
            args["title"] = title
        if location:
            args["location"] = location

        return await self.c.call("search_people", args)

    async def get_person_profile(self, profile_url_or_username: str, sections: Optional[List[str]] = None) -> Any:
        """Get profile details for a specified user profile URL or username via MCP."""
        username = extract_username(profile_url_or_username)
        args: Dict[str, Any] = {"linkedin_username": username}
        if sections:
            args["sections"] = ",".join(sections)
        return await self.c.call("get_person_profile", args)

    async def connect_with_person(self, profile_url_or_username: str, note: Optional[str] = None) -> Any:
        """Send a connection request with an optional note via MCP."""
        username = extract_username(profile_url_or_username)
        args: Dict[str, Any] = {"linkedin_username": username}
        if note:
            args["note"] = note
        return await self.c.call("connect_with_person", args)

    async def get_my_profile(self, sections: Optional[List[str]] = None) -> Any:
        """Get current logged-in user profile details via MCP."""
        args: Dict[str, Any] = {}
        if sections:
            args["sections"] = ",".join(sections)
        return await self.c.call("get_my_profile", args)
