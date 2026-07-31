import sys
import asyncio
import logging
import random
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright
from app.config import settings
from app.linkedin.comment_like import human_type

logger = logging.getLogger(__name__)


async def _connect_via_playwright_impl(profile_url: str, note: Optional[str] = None) -> Dict[str, Any]:
    """Playwright browser automation to send a LinkedIn connection request with custom AI note."""
    result: Dict[str, Any] = {"connected": False, "error": None, "details": None}

    mcp_profile_dir = Path.home() / ".linkedin-mcp" / "profile"
    storage = Path(settings.PLAYWRIGHT_STORAGE)

    try:
        async with async_playwright() as p:
            context = None
            browser = None

            if mcp_profile_dir.exists():
                logger.info(f"Launching Playwright for connect with profile from {mcp_profile_dir}")
                try:
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir=str(mcp_profile_dir),
                        headless=settings.HEADLESS,
                        slow_mo=60,
                        viewport={"width": 1366, "height": 900}
                    )
                except Exception as pe:
                    logger.warning(f"Persistent context launch failed ({pe}). Falling back to standard browser...")

            if not context:
                try:
                    browser = await p.chromium.launch(headless=settings.HEADLESS, slow_mo=60)
                except Exception:
                    try:
                        browser = await p.chromium.launch(headless=settings.HEADLESS, slow_mo=60, channel="chrome")
                    except Exception:
                        browser = await p.chromium.launch(headless=settings.HEADLESS, slow_mo=60, channel="msedge")

                context_kwargs = {"viewport": {"width": 1366, "height": 900}}
                if storage.exists():
                    context_kwargs["storage_state"] = str(storage)
                context = await browser.new_context(**context_kwargs)

            page = await context.new_page()

            try:
                logger.info(f"Navigating to profile: {profile_url}")
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(random.uniform(3.5, 6.0))

                # Look for direct Connect button
                connect_btn = None
                connect_selectors = [
                    'button.artdeco-button--primary:has-text("Connect")',
                    'button[aria-label*="Invite"][aria-label*="connect"]',
                    'button:has-text("Connect")',
                ]

                for sel in connect_selectors:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        connect_btn = loc
                        break

                # If not visible directly, check under 'More' action dropdown menu
                if not connect_btn:
                    more_selectors = [
                        'button.artdeco-dropdown__trigger:has-text("More")',
                        'button[aria-label="More actions"]',
                        'button:has-text("More")',
                    ]
                    for m_sel in more_selectors:
                        m_btn = page.locator(m_sel).first
                        if await m_btn.count() > 0 and await m_btn.is_visible():
                            logger.info("Clicking 'More' dropdown to reveal Connect button...")
                            await m_btn.hover()
                            await asyncio.sleep(random.uniform(0.5, 1.0))
                            await m_btn.click()
                            await asyncio.sleep(random.uniform(1.0, 2.0))
                            break

                    # Re-check for Connect inside dropdown menu
                    dropdown_connect_selectors = [
                        'div.artdeco-dropdown__content button:has-text("Connect")',
                        'div.artdeco-dropdown__content li:has-text("Connect")',
                        'button:has-text("Connect")',
                    ]
                    for sel in dropdown_connect_selectors:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            connect_btn = loc
                            break

                if not connect_btn:
                    raise RuntimeError("Connect button not found on profile. Connection may already be pending or 1st-degree.")

                logger.info("Hovering and clicking Connect button...")
                await connect_btn.hover()
                await asyncio.sleep(random.uniform(0.6, 1.2))
                await connect_btn.click()
                await asyncio.sleep(random.uniform(1.5, 3.0))

                # Handle Add Note Modal
                if note:
                    add_note_btn = page.locator('button:has-text("Add a note")').first
                    if await add_note_btn.count() > 0 and await add_note_btn.is_visible():
                        logger.info("Clicking 'Add a note' modal button...")
                        await add_note_btn.click()
                        await asyncio.sleep(random.uniform(1.0, 2.0))

                        note_box = page.locator('textarea[name="message"], textarea#custom-message').first
                        if await note_box.count() > 0:
                            await human_type(note_box, note)
                            await asyncio.sleep(random.uniform(1.5, 3.0))

                # Send request
                send_btn = None
                send_selectors = [
                    'button.artdeco-button--primary:has-text("Send")',
                    'button[aria-label*="Send"]',
                    'button:has-text("Send without a note")',
                    'button:has-text("Send")',
                ]
                for s_sel in send_selectors:
                    loc = page.locator(s_sel).first
                    if await loc.count() > 0 and await loc.is_enabled():
                        send_btn = loc
                        break

                if send_btn:
                    await send_btn.hover()
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    await send_btn.click()
                    result["connected"] = True
                    result["details"] = "Connection request sent successfully via Playwright."
                    logger.info(f"Connection request successfully sent for profile: {profile_url}")
                else:
                    raise RuntimeError("Send connection button not found in modal.")

                await asyncio.sleep(random.uniform(3.0, 6.0))

            except Exception as e:
                result["error"] = str(e)
                logger.exception(f"Playwright connect failed for {profile_url}: {e}")
            finally:
                await page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()

    except Exception as outer_e:
        result["error"] = str(outer_e)
        logger.exception(f"Playwright browser initialization failed: {outer_e}")

    return result


def _run_connect_in_proactor(profile_url: str, note: Optional[str] = None) -> Dict[str, Any]:
    """Execute connect coroutine inside a clean Proactor event loop thread on Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_connect_via_playwright_impl(profile_url, note))
    finally:
        loop.close()


async def connect_via_playwright(profile_url: str, note: Optional[str] = None) -> Dict[str, Any]:
    """Public wrapper executing Playwright connect in an event loop thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_connect_in_proactor, profile_url, note)
