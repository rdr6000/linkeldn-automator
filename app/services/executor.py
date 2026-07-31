import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from app.mcp.client import LinkedInMCP
from app.mcp.tools import MCPTools
from app.linkedin.comment_like import comment_and_like
from app.linkedin.connect import connect_via_playwright

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Executes LinkedIn actions:
    - 'comment': Calls Playwright (comment_and_like)
    - 'connect': Calls MCP connect_with_person with automatic Playwright fallback, note-limit recovery, and detailed logging
    """

    def __init__(
        self,
        mcp_client: Optional[LinkedInMCP] = None,
        comment_func: Optional[Callable[[str, str], Awaitable[Dict[str, Any]]]] = None,
        connect_func: Optional[Callable[[str, Optional[str]], Awaitable[Dict[str, Any]]]] = None
    ):
        self.mcp_client = mcp_client or LinkedInMCP()
        self.comment_func = comment_func or comment_and_like
        self.connect_func = connect_func or connect_via_playwright

    async def execute_comment_action(self, target_url: str, comment_text: str) -> Dict[str, Any]:
        """Comment + Like via custom Playwright code."""
        logger.info(f"Executing comment action on {target_url}")
        res = await self.comment_func(target_url, comment_text)
        success = res.get("commented", False)
        return {
            "success": success,
            "commented": res.get("commented", False),
            "liked": res.get("liked", False),
            "error": res.get("error"),
            "via": "playwright"
        }

    async def execute_connect_action(self, target_url: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Send connection request using MCP with note-limit detection, Playwright fallback, and detailed logs."""
        logger.info(f"Executing connect action on {target_url} via MCP")
        tools = MCPTools(self.mcp_client)
        
        mcp_error = None
        note_limit_hit = False

        try:
            raw_mcp = await tools.connect_with_person(
                profile_url_or_username=target_url,
                note=note
            )
            logger.info(f"Detailed MCP response for {target_url}: {raw_mcp}")

            is_mcp_success = True
            if isinstance(raw_mcp, dict):
                status_str = str(raw_mcp.get("status", "")).lower()
                note_sent = raw_mcp.get("note_sent")

                if status_str == "custom_note_limit_reached" or note_sent is False:
                    is_mcp_success = False
                    note_limit_hit = True
                    mcp_error = f"LinkedIn monthly custom note limit reached ({raw_mcp.get('status')})."
                elif status_str in ["error", "failed", "failure"] or raw_mcp.get("success") is False or "error" in raw_mcp:
                    is_mcp_success = False
                    mcp_error = str(raw_mcp.get("message") or raw_mcp.get("error") or raw_mcp)

            elif isinstance(raw_mcp, str):
                if any(err in raw_mcp.lower() for err in ["error", "failed", "could not find", "not found", "unable", "cannot", "limit_reached"]):
                    is_mcp_success = False
                    mcp_error = raw_mcp

            if is_mcp_success:
                return {
                    "success": True,
                    "via": "mcp",
                    "details": "Connection request sent successfully via MCP with custom note.",
                    "mcp_output": raw_mcp
                }

        except Exception as e:
            mcp_error = str(e)
            logger.warning(f"MCP connect_with_person threw exception for {target_url}: {e}")

        # Handling case where LinkedIn custom note monthly limit was reached
        if note_limit_hit:
            logger.info(f"LinkedIn custom note limit reached for {target_url}. Retrying connect WITHOUT note...")
            try:
                raw_mcp_no_note = await tools.connect_with_person(
                    profile_url_or_username=target_url,
                    note=None
                )
                status_no_note = str(raw_mcp_no_note.get("status", "")).lower() if isinstance(raw_mcp_no_note, dict) else ""
                if status_no_note not in ["error", "failed", "custom_note_limit_reached"]:
                    return {
                        "success": True,
                        "via": "mcp_without_note",
                        "details": "Connection request sent successfully WITHOUT note (LinkedIn monthly custom note limit reached).",
                        "mcp_output": raw_mcp_no_note
                    }
            except Exception as no_note_e:
                logger.warning(f"MCP connect without note failed: {no_note_e}")

        # Playwright Fallback (Retry connection without note if custom note limit hit, or with note if standard failure)
        logger.info(f"Triggering Playwright fallback connect for {target_url} (MCP log: {mcp_error})...")
        fallback_note = None if note_limit_hit else note
        pw_res = await self.connect_func(target_url, fallback_note)
        
        if pw_res.get("connected"):
            note_status = "without note" if (note_limit_hit or not fallback_note) else "with custom note"
            return {
                "success": True,
                "via": "playwright_fallback",
                "details": f"Connection request sent via Playwright fallback {note_status}.",
                "mcp_log": mcp_error,
                "playwright_details": pw_res.get("details")
            }
        else:
            return {
                "success": False,
                "via": "mcp_and_playwright",
                "error": f"MCP Status: {mcp_error} | Playwright Fallback Error: {pw_res.get('error')}",
                "mcp_log": mcp_error,
                "playwright_error": pw_res.get("error")
            }
