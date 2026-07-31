```markdown
# LinkedIn Daily Automation System
### MCP-First Architecture + Minimal Custom Code

**Design principle**  
Use `stickerdaniel/linkedin-mcp-server` for **everything it supports**.  
Write custom Playwright code **only** for the missing pieces:

| Action                        | Tool / Method                          | Source      |
|-------------------------------|----------------------------------------|-------------|
| Get home feed posts           | `get_feed`                             | MCP         |
| Search posts by keyword       | `search_posts`                         | MCP         |
| Search people                 | `search_people`                        | MCP         |
| Get profile details           | `get_person_profile`                   | MCP         |
| Send connection request       | `connect_with_person`                  | MCP         |
| **Comment on a post**         | Custom Playwright                      | Custom only |
| **Like a post**               | Custom Playwright                      | Custom only |
| Detect & skip ads             | Client-side filter on MCP data         | Custom      |
| Generate text                 | Gemini                                 | Custom      |

This keeps the codebase small and leverages the maintained MCP server for all reading and most writing.

---

## 1. High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Web UI / Scheduler                                         │
│  (Approval mode or Autonomous mode)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Job Runner                                                 │
│  1. MCP → get_feed + search_posts + search_people           │
│  2. Filter ads + already-processed                          │
│  3. Gemini → generate comments / notes                      │
│  4. If Approval → save PendingActions & wait                │
│  5. If Autonomous (or after approve) → execute              │
└────────┬───────────────────────────────┬────────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────────┐      ┌──────────────────────────────┐
│ MCP                 │      │ Custom Playwright            │
│ • connect_with_     │      │ • comment_on_post()          │
│   person            │      │ • like_post()                │
│ • (future tools)    │      │ • (fallback connect)         │
└─────────────────────┘      └──────────────────────────────┘
```

---

## 2. Project Structure (MCP-First)

```text
linkedin-auto/
├── .env
├── config.yaml
├── requirements.txt
├── main.py
├── app/
│   ├── main.py                     # FastAPI
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── gemini_client.py
│   ├── mcp/
│   │   ├── client.py               # Thin wrapper around MCP HTTP/stdio
│   │   └── tools.py                # Typed helpers for each MCP tool
│   ├── linkedin/
│   │   ├── comment_like.py         # ONLY custom browser code
│   │   └── ad_filter.py            # Pure Python filter
│   ├── services/
│   │   ├── collector.py            # Uses MCP only
│   │   ├── generator.py            # Gemini
│   │   ├── executor.py             # Calls MCP or custom
│   │   ├── job_runner.py
│   │   └── approval.py
│   ├── routers/
│   │   ├── dashboard.py
│   │   ├── jobs.py
│   │   ├── approvals.py
│   │   └── settings.py
│   └── templates/ ...
├── data/
│   ├── history.db
│   └── cookies.json                # only needed for the custom comment/like browser
└── scripts/
    ├── test_mcp.py
    └── test_comment_like.py
```

---

## 3. MCP Client Wrapper

```python
# app/mcp/client.py
import httpx
import uuid
import json
from typing import Any
from app.config import settings

class LinkedInMCP:
    def __init__(self, base_url: str = None):
        self.url = base_url or settings.MCP_URL
        self.session_id = None

    async def call(self, tool_name: str, arguments: dict = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            # Handle session header if present
            if "Mcp-Session-Id" in resp.headers:
                self.session_id = resp.headers["Mcp-Session-Id"]
            data = resp.json()
            # MCP returns result inside content / structured content
            return self._extract_result(data)

    def _extract_result(self, data: dict) -> Any:
        # Adjust according to actual MCP response shape
        if "result" in data:
            content = data["result"].get("content", [])
            if content and isinstance(content, list):
                # Most tools return text or JSON string
                text = content[0].get("text", "")
                try:
                    return json.loads(text)
                except Exception:
                    return text
            return data["result"]
        raise Exception(f"MCP error: {data}")

# Convenience helpers
class MCPTools:
    def __init__(self, client: LinkedInMCP):
        self.c = client

    async def get_feed(self, limit: int = 50):
        return await self.c.call("get_feed", {"limit": limit})

    async def search_posts(self, keywords: str, recency: str = "past-week"):
        return await self.c.call("search_posts", {
            "keywords": keywords,
            "recency": recency
        })

    async def search_people(self, keywords: str, connection_degree: str = "2nd"):
        return await self.c.call("search_people", {
            "keywords": keywords,
            "connection_degree": connection_degree
        })

    async def get_person_profile(self, profile_url: str, sections: list = None):
        return await self.c.call("get_person_profile", {
            "profile_url": profile_url,
            "sections": sections or ["experience", "about", "posts"]
        })

    async def connect_with_person(self, profile_url: str, note: str = None):
        args = {"profile_url": profile_url}
        if note:
            args["note"] = note
        return await self.c.call("connect_with_person", args)
```

---

## 4. Collector – 100% MCP

```python
# app/services/collector.py
from app.mcp.client import LinkedInMCP, MCPTools
from app.linkedin.ad_filter import is_ad_post
from app.config import settings

async def collect_posts_and_people() -> tuple[list[dict], list[dict]]:
    mcp = LinkedInMCP()
    tools = MCPTools(mcp)

    posts = []
    people = []

    # 1. Home Feed
    if settings.feed.enabled:
        feed = await tools.get_feed(limit=settings.daily_limits.max_feed_posts)
        for item in normalize_feed(feed):          # normalize MCP shape → standard dict
            if is_ad_post(item):
                continue
            posts.append({**item, "source": "feed"})

    # 2. Keyword search posts
    for kw in settings.keywords:
        results = await tools.search_posts(kw, recency=settings.recency)
        for item in normalize_posts(results):
            if is_ad_post(item):
                continue
            posts.append({**item, "source": "search", "keyword": kw})

    # 3. Keyword search people
    for kw in settings.keywords:
        results = await tools.search_people(kw)
        for person in normalize_people(results):
            people.append({**person, "keyword": kw})

    # Deduplicate by URL
    posts = dedup_by_url(posts)
    people = dedup_by_url(people)

    return posts, people
```

**Ad filter** (pure Python – works on whatever text/fields MCP returns):

```python
# app/linkedin/ad_filter.py
AD_KEYWORDS = [
    "promoted", "sponsored", "promoted by", "sponsored by",
    "paid partnership", "ad ", "• promoted"
]

def is_ad_post(post: dict) -> bool:
    text = (post.get("text") or "") + " " + (post.get("actor_subdescription") or "")
    text = text.lower()
    return any(k in text for k in AD_KEYWORDS)
```

---

## 5. Custom Code – Only Comment + Like

This is the **only** place we use Playwright.

```python
# app/linkedin/comment_like.py
from playwright.async_api import async_playwright
from pathlib import Path
from app.config import settings
import asyncio
import random
import logging

async def comment_and_like(post_url: str, comment_text: str) -> dict:
    """
    Returns {"commented": bool, "liked": bool, "error": str|None}
    """
    result = {"commented": False, "liked": False, "error": None}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=settings.HEADLESS,
            slow_mo=60
        )
        storage = Path(settings.PLAYWRIGHT_STORAGE)
        context = await browser.new_context(
            storage_state=str(storage) if storage.exists() else None,
            viewport={"width": 1366, "height": 900}
        )
        page = await context.new_page()

        try:
            await page.goto(post_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(random.uniform(3.5, 7))

            # ----- COMMENT -----
            box = None
            for sel in [
                'div.ql-editor[data-placeholder*="Add a comment"]',
                'div.ql-editor[data-placeholder*="comment"]',
                'div[role="textbox"].ql-editor',
                'div.comments-comment-box__editor div.ql-editor',
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    box = loc
                    break
            if not box:
                raise Exception("Comment box not found")

            await box.click()
            await asyncio.sleep(random.uniform(0.6, 1.4))
            await box.fill("")
            await box.type(comment_text, delay=random.randint(25, 55))
            await asyncio.sleep(random.uniform(1.0, 2.3))

            submitted = False
            for sel in [
                'button.comments-comment-box__submit-button--cr',
                'button.comments-comment-box__submit-button',
                'button:has-text("Comment")',
                'button:has-text("Post")',
            ]:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_enabled():
                    await btn.click()
                    submitted = True
                    break
            if not submitted:
                raise Exception("Submit button not found")

            result["commented"] = True
            await asyncio.sleep(random.uniform(2.5, 5))

            # ----- LIKE -----
            for sel in [
                'button[aria-label*="Like"][aria-pressed="false"]',
                'button.react-button__trigger[aria-pressed="false"]',
                'button:has-text("Like")',
            ]:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    pressed = await btn.get_attribute("aria-pressed")
                    if pressed != "true":
                        await btn.click()
                        await asyncio.sleep(random.uniform(1.0, 2.5))
                    result["liked"] = True
                    break

        except Exception as e:
            result["error"] = str(e)
            logging.exception(f"comment_and_like failed: {post_url}")
        finally:
            await context.close()
            await browser.close()

    return result
```

---

## 6. Executor – MCP first, custom only when needed

```python
# app/services/executor.py
from app.mcp.client import LinkedInMCP, MCPTools
from app.linkedin.comment_like import comment_and_like

async def execute_comment_action(action):
    """Comment + Like (custom code only)"""
    return await comment_and_like(action.target_url, action.generated_text)

async def execute_connect_action(action):
    """Prefer MCP. Fall back to custom only if MCP fails."""
    mcp = LinkedInMCP()
    tools = MCPTools(mcp)
    try:
        result = await tools.connect_with_person(
            profile_url=action.target_url,
            note=action.generated_text
        )
        return {"success": True, "via": "mcp", "raw": result}
    except Exception as e:
        # Optional: implement a pure Playwright connect fallback here
        return {"success": False, "error": str(e), "via": "mcp"}
```

---

## 7. Job Runner (MCP-centric)

```python
async def run_job(job_id: int, mode: str):
    # 1. Collect everything via MCP
    posts, people = await collect_posts_and_people()

    # 2. Filter already done + apply daily limits
    posts = await filter_new(posts, action_type="comment")
    people = await filter_new(people, action_type="connect")

    posts = posts[:settings.daily_limits.comments]
    people = people[:settings.daily_limits.connections]

    # 3. Generate with Gemini
    pending_actions = []
    for p in posts:
        comment = await generate_comment(p["text"], p["author"], settings.comment_style)
        pending_actions.append(PendingAction(
            job_id=job_id,
            action_type="comment",
            target_url=p["url"],
            target_name=p["author"],
            original_text=p["text"][:1500],
            generated_text=comment,
            status="pending" if mode == "approval" else "approved"
        ))

    for person in people:
        note = await generate_connection_note(...)
        pending_actions.append(...)

    await save_pending(pending_actions)

    if mode == "approval":
        await set_job_status(job_id, "waiting_approval")
        return

    # 4. Autonomous execution
    for action in pending_actions:
        if action.action_type == "comment":
            result = await execute_comment_action(action)
            # update DB with commented + liked
        else:
            result = await execute_connect_action(action)
        await human_delay()
```

---

## 8. Web UI Modes (unchanged conceptually)

- **Approval mode** (default)  
  MCP collects → Gemini generates → you review in UI → on Approve the system calls:
  - `comment_and_like()` for comments
  - `MCP.connect_with_person()` for connections

- **Autonomous mode**  
  Same pipeline but skips the UI and executes immediately.

---

## 9. First-Time Setup

1. Start the MCP server and log in once:
   ```bash
   uvx mcp-server-linkedin@latest --transport streamable-http --port 8000
   ```
2. Export cookies for the **custom** comment/like browser (only needed once):
   ```bash
   python scripts/export_cookies.py
   ```
3. Test MCP tools:
   ```bash
   python scripts/test_mcp.py
   ```
4. Test one comment + like:
   ```bash
   python scripts/test_comment_like.py "https://www.linkedin.com/posts/..."
   ```
5. Launch the web UI:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

## 10. What You Should Never Re-implement

Do **not** write custom scrapers for:
- Home feed
- Keyword post search
- People search
- Profile details
- Connection requests (use MCP first)

Only maintain the small `comment_like.py` module.  
When the MCP server adds a `comment_on_post` or `react_to_post` tool in the future, you can delete the custom code.

---
