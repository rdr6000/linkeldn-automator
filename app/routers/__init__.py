from app.routers.dashboard import router as dashboard_router
from app.routers.jobs import router as jobs_router
from app.routers.approvals import router as approvals_router
from app.routers.settings import router as settings_router
from app.routers.analytics import router as analytics_router

__all__ = [
    "dashboard_router",
    "jobs_router",
    "approvals_router",
    "settings_router",
    "analytics_router",
]
