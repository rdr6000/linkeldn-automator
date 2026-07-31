import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import settings

async def export_cookies():
    """
    Launches a browser window for logging in to LinkedIn manually once,
    then saves storage state / cookies to data/cookies.json for custom Playwright automation.
    """
    storage_path = Path(settings.PLAYWRIGHT_STORAGE)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    print("Launching browser for LinkedIn cookie export...")
    print("Please log in to LinkedIn in the opened browser window if prompted.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await context.new_page()

        await page.goto("https://www.linkedin.com/login")
        print("\nPress ENTER in terminal once you are logged in and viewing the LinkedIn home feed...")
        input()

        await context.storage_state(path=str(storage_path))
        print(f"Successfully saved authentication cookies to: {storage_path}")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(export_cookies())
