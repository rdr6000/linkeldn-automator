import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.routers import (
    dashboard_router,
    jobs_router,
    approvals_router,
    settings_router,
    analytics_router
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("linkedin_auto")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database table initialization and shutdown."""
    logger.info("Initializing database tables...")
    init_db()
    logger.info("Application startup completed successfully.")
    yield


app = FastAPI(
    title="LinkedIn Daily Automation System",
    description="MCP-First LinkedIn Automation with Minimal Custom Browser Code",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include routers
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(approvals_router)
app.include_router(settings_router)
app.include_router(analytics_router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "LinkedIn Automation System"}
