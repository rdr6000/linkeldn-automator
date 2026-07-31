import logging
from typing import List, Dict, Any, Tuple, Optional
from app.mcp.client import LinkedInMCP
from app.mcp.tools import MCPTools
from app.linkedin.ad_filter import is_ad_post
from app.config import settings

logger = logging.getLogger(__name__)


def extract_target_label(url: str, text: str) -> str:
    """Extract a human-friendly label for a post target from URL slug or post content preview."""
    if "/posts/" in url:
        try:
            slug = url.split("/posts/")[1].split("?")[0].split("-")
            clean_parts = []
            for p in slug:
                p_clean = p.split("_")[0]
                if p_clean.lower() not in ["urn", "li", "activity", "ugcpost", "share", "post"] and not p_clean.isdigit() and len(p_clean) > 1:
                    # Filter out alphanumeric hash tokens (e.g. b23575212 or 991823)
                    if not (any(c.isdigit() for c in p_clean) and any(c.isalpha() for c in p_clean)):
                        clean_parts.append(p_clean)
            if clean_parts:
                candidate_name = " ".join(clean_parts[:3]).title()
                if len(candidate_name) > 3:
                    return candidate_name
        except Exception:
            pass

    elif "/in/" in url:
        try:
            slug = url.split("/in/")[1].split("/")[0].split("?")[0]
            if slug:
                return slug.replace("-", " ").title()
        except Exception:
            pass

    # Fallback to snippet of post text or generic title
    if text and len(text.strip()) > 5:
        clean_text = text.strip()
        first_line = clean_text.split("\n")[0]
        return first_line[:50] + ("..." if len(first_line) > 50 else "")

    return "LinkedIn Target Post"


def normalize_feed(feed: Any) -> List[Dict[str, Any]]:
    """Normalize MCP feed or search_posts response into standard dictionaries with robust author/target extraction."""
    if not feed:
        return []

    items = []

    if isinstance(feed, dict):
        refs = feed.get("references", {})
        if isinstance(refs, dict):
            for key in ["feed", "search_results", "posts", "items"]:
                if key in refs and isinstance(refs[key], list):
                    items.extend(refs[key])
        if not items and "posts" in feed:
            items = feed["posts"]
        elif not items and "items" in feed:
            items = feed["items"]

    elif isinstance(feed, list):
        items = feed

    normalized = []
    for item in items:
        if isinstance(item, dict):
            raw_url = item.get("url") or item.get("link") or item.get("post_url") or ""
            if raw_url.startswith("/"):
                url = f"https://www.linkedin.com{raw_url}"
            else:
                url = raw_url

            text = item.get("text") or item.get("content") or item.get("commentary") or ""
            subdesc = item.get("actor_subdescription") or item.get("headline") or ""

            # Robust author & target name extraction
            raw_author = (
                item.get("author") or
                item.get("actor_name") or
                item.get("name") or
                item.get("author_name") or
                item.get("actor")
            )

            if isinstance(raw_author, dict):
                author = raw_author.get("name") or raw_author.get("text") or ""
            elif isinstance(raw_author, str) and raw_author.strip() and not raw_author.startswith("http"):
                author = raw_author.strip()
            else:
                author = ""

            if not author or author == "LinkedIn User":
                author = extract_target_label(url, text)

            if url:
                normalized.append({
                    "url": url,
                    "author": author,
                    "text": text,
                    "actor_subdescription": subdesc,
                    "raw": item
                })
    return normalized


def normalize_posts(results: Any) -> List[Dict[str, Any]]:
    """Normalize MCP search_posts response into standard dictionaries."""
    return normalize_feed(results)


def normalize_people(results: Any) -> List[Dict[str, Any]]:
    """Normalize MCP search_people response into standard dictionaries."""
    if not results:
        return []

    items = []

    if isinstance(results, dict):
        refs = results.get("references", {})
        if isinstance(refs, dict):
            for key in ["search_results", "people", "items"]:
                if key in refs and isinstance(refs[key], list):
                    items.extend(refs[key])
        if not items and "people" in results:
            items = results["people"]
        elif not items and "results" in results:
            items = results["results"]

    elif isinstance(results, list):
        items = results

    normalized = []
    for p in items:
        if isinstance(p, dict):
            raw_url = p.get("profile_url") or p.get("url") or p.get("link") or ""
            username = p.get("linkedin_username") or p.get("username") or ""
            if raw_url.startswith("/"):
                url = f"https://www.linkedin.com{raw_url}"
            elif not raw_url and username:
                url = f"https://www.linkedin.com/in/{username}"
            else:
                url = raw_url

            name = p.get("name") or p.get("text") or p.get("title") or username or ""
            if not name or name == "LinkedIn User":
                name = extract_target_label(url, "")

            headline = p.get("headline") or p.get("occupation") or p.get("subdescription") or ""
            if url:
                normalized.append({
                    "url": url,
                    "username": username,
                    "name": name,
                    "headline": headline,
                    "raw": p
                })
    return normalized


def dedup_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate list of dictionaries by 'url' key while preserving priority order."""
    seen = set()
    unique = []
    for item in items:
        url = item.get("url", "").strip().lower()
        if url and url not in seen:
            seen.add(url)
            unique.append(item)
    return unique


async def collect_posts_and_people(mcp_client: Optional[LinkedInMCP] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    100% MCP-based collector following strict priority ordering:
    1. First: Home Feed posts (bypassing ads via is_ad_post)
    2. Second: Keyword Search posts (bypassing ads via is_ad_post, respects search limit per term)
    3. Third: Keyword Search people profiles (respects search limit per term)
    """
    mcp = mcp_client or LinkedInMCP()
    tools = MCPTools(mcp)

    posts: List[Dict[str, Any]] = []
    people: List[Dict[str, Any]] = []

    # 1. FIRST PRIORITY: Home Feed Posts
    if settings.feed.enabled:
        try:
            logger.info("Fetching home feed posts first via MCP...")
            feed_raw = await tools.get_feed(limit=settings.daily_limits.max_feed_posts)
            feed_items = normalize_feed(feed_raw)
            for item in feed_items:
                if is_ad_post(item):
                    logger.info(f"Ad filter triggered: Bypassing sponsored feed post {item.get('url')}")
                    continue
                posts.append({**item, "source": "feed"})
        except Exception as e:
            logger.error(f"Error collecting home feed posts: {e}")

    # 2. SECOND PRIORITY: Search Posts by Keyword
    max_search_posts = getattr(settings.search, "max_posts_per_keyword", 3)
    for kw in settings.keywords:
        try:
            logger.info(f"Searching posts for keyword '{kw}' (limit: {max_search_posts}) via MCP...")
            results_raw = await tools.search_posts(
                keywords=kw,
                recency=settings.recency,
                sort_by=settings.search.sort_by,
                content_type=settings.search.content_type
            )
            search_items = normalize_posts(results_raw)[:max_search_posts]
            for item in search_items:
                if is_ad_post(item):
                    logger.info(f"Ad filter triggered: Bypassing sponsored search post {item.get('url')}")
                    continue
                posts.append({**item, "source": "search", "keyword": kw})
        except Exception as e:
            logger.error(f"Error searching posts for keyword '{kw}': {e}")

    # 3. THIRD PRIORITY: Search People by Keyword
    max_search_people = getattr(settings.search, "max_people_per_keyword", 3)
    for kw in settings.keywords:
        try:
            logger.info(f"Searching people for keyword '{kw}' (limit: {max_search_people}) via MCP...")
            people_raw = await tools.search_people(
                keywords=kw,
                connection_degree=settings.search.network_degree,
                title=settings.search.title_filter or None,
                location=settings.search.location_filter or None
            )
            search_people_items = normalize_people(people_raw)[:max_search_people]
            for person in search_people_items:
                people.append({**person, "keyword": kw})
        except Exception as e:
            logger.error(f"Error searching people for keyword '{kw}': {e}")

    # Deduplicate while preserving feed -> search priority
    posts = dedup_by_url(posts)
    people = dedup_by_url(people)

    logger.info(f"Collector finished. Priority collection gathered {len(posts)} posts and {len(people)} people profiles (all ads bypassed).")
    return posts, people
