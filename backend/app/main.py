"""FastAPI application entry point for ARGUS."""

from fastapi import FastAPI

from app.api.analyze import router as analyze_router
from app.api.health import router as health_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(analyze_router)
    app.include_router(health_router)
    return app


app = create_app()
