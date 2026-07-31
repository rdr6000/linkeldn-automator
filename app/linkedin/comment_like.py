import sys
import asyncio
import logging
import random
from pathlib import Path
from typing import Dict, Any
from playwright.async_api import async_playwright
from app.config import settings

logger = logging.getLogger(__name__)


async def human_type(locator, text: str):
    """
    Simulate realistic human typing with per-character keystroke variance,
    punctuation pauses, shift overhead, and natural mid-sentence hesitations.
    """
    await locator.click()
    await asyncio.sleep(random.uniform(0.6, 1.4))

    for char in text:
        await locator.type(char, delay=0)

        if char in [".", "!", "?"]:
            # End of sentence pause for thought
            await asyncio.sleep(random.uniform(0.45, 0.95))
        elif char in [",", ";", ":", "-"]:
            # Clause boundary pause
            await asyncio.sleep(random.uniform(0.25, 0.55))
        elif char == " ":
            # Space between words with occasional mid-sentence hesitation
            if random.random() < 0.12:
                await asyncio.sleep(random.uniform(0.35, 0.75))
            else:
                await asyncio.sleep(random.uniform(0.08, 0.18))
        elif char.isupper():
            # Shift key overhead
            await asyncio.sleep(random.uniform(0.10, 0.22))
        else:
            # Standard keystroke timing
            await asyncio.sleep(random.uniform(0.045, 0.125))


async def _comment_and_like_impl(post_url: str, comment_text: str) -> Dict[str, Any]:
    """Playwright browser implementation for commenting and liking with anti-bot human behavior simulation."""
    result: Dict[str, Any] = {"commented": False, "liked": False, "error": None}

    mcp_profile_dir = Path.home() / ".linkedin-mcp" / "profile"
    storage = Path(settings.PLAYWRIGHT_STORAGE)

    try:
        async with async_playwright() as p:
            context = None
            browser = None

            # 1. Use MCP persistent logged-in profile if available
            if mcp_profile_dir.exists():
                logger.info(f"Launching Playwright with logged-in MCP profile from {mcp_profile_dir}")
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
                logger.info(f"Navigating to post: {post_url}")
                await page.goto(post_url, wait_until="domcontentloaded", timeout=45000)

                # Simulate human reading post before acting (4.0 to 7.5 seconds)
                await asyncio.sleep(random.uniform(4.0, 7.5))

                # Human scrolling behavior
                await page.evaluate(f"window.scrollBy(0, {random.randint(180, 380)})")
                await asyncio.sleep(random.uniform(1.2, 2.5))

                box = None
                box_selectors = [
                    'div.ql-editor[data-placeholder*="Add a comment"]',
                    'div.ql-editor[data-placeholder*="comment"]',
                    'div[role="textbox"].ql-editor',
                    'div.comments-comment-box__editor div.ql-editor',
                    'div.comments-comment-box__content div[role="textbox"]',
                    'div[contenteditable="true"]',
                ]

                # Check if box is already present and visible
                for sel in box_selectors:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        box = loc
                        break

                # If not present/visible, click the Comment action button to open editor
                if not box:
                    trigger_selectors = [
                        'button.comment-button',
                        'button[aria-label*="Comment"]',
                        'button:has-text("Comment")',
                        'span:has-text("Comment")',
                    ]
                    for t_sel in trigger_selectors:
                        t_btn = page.locator(t_sel).first
                        if await t_btn.count() > 0 and await t_btn.is_visible():
                            logger.info(f"Hovering and clicking Comment trigger button: {t_sel}")
                            await t_btn.hover()
                            await asyncio.sleep(random.uniform(0.5, 1.2))
                            await t_btn.click()
                            await asyncio.sleep(random.uniform(1.5, 3.0))
                            break

                    # Re-check for box after clicking trigger
                    for sel in box_selectors:
                        loc = page.locator(sel).first
                        if await loc.count() > 0:
                            box = loc
                            break

                if not box:
                    raise RuntimeError("Comment box selector not found on page. Please ensure logged-in session profile is valid.")

                await box.scroll_into_view_if_needed()
                await box.hover()
                await asyncio.sleep(random.uniform(0.4, 0.9))

                # Human typing simulation
                logger.info(f"Simulating human typing for post comment...")
                await human_type(box, comment_text)

                # Human proofreading pause after typing (2.5 to 5.0 seconds)
                logger.info("Human proofreading pause before submitting comment...")
                await asyncio.sleep(random.uniform(2.5, 5.0))

                # Submit Comment
                submitted = False
                submit_selectors = [
                    'button.comments-comment-box__submit-button--cr',
                    'button.comments-comment-box__submit-button',
                    'button.comments-comment-box__submit-btn',
                    'button:has-text("Comment")',
                    'button:has-text("Post")',
                ]
                for sel in submit_selectors:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_enabled():
                        await btn.hover()
                        await asyncio.sleep(random.uniform(0.6, 1.3))
                        await btn.click()
                        submitted = True
                        break

                if not submitted:
                    raise RuntimeError("Submit comment button not found or disabled")

                result["commented"] = True
                logger.info(f"Comment successfully submitted for post {post_url}")
                await asyncio.sleep(random.uniform(3.0, 5.5))

                # ----- LIKE -----
                like_selectors = [
                    'button[aria-label*="Like"][aria-pressed="false"]',
                    'button.react-button__trigger[aria-pressed="false"]',
                    'button:has-text("Like")',
                ]
                for sel in like_selectors:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        pressed = await btn.get_attribute("aria-pressed")
                        if pressed != "true":
                            await btn.hover()
                            await asyncio.sleep(random.uniform(0.5, 1.1))
                            await btn.click()
                            await asyncio.sleep(random.uniform(1.5, 3.0))
                        result["liked"] = True
                        logger.info(f"Like successfully registered for post {post_url}")
                        break

                # Post-submission human lingering delay before leaving page (3.5 to 7.0 seconds)
                await asyncio.sleep(random.uniform(3.5, 7.0))

            except Exception as e:
                result["error"] = str(e)
                logger.exception(f"comment_and_like failed for URL {post_url}: {e}")
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


def _run_in_proactor_loop(post_url: str, comment_text: str) -> Dict[str, Any]:
    """Execute coroutine inside a clean Proactor event loop thread on Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_comment_and_like_impl(post_url, comment_text))
    finally:
        loop.close()


async def comment_and_like(post_url: str, comment_text: str) -> Dict[str, Any]:
    """Public wrapper that guarantees execution inside a Windows Proactor thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_in_proactor_loop, post_url, comment_text)
