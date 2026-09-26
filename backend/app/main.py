"""FastAPI application entry point for ARGUS."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.analyze import router as analyze_router
from app.api.health import router as health_router
from app.api.portfolio import router as portfolio_router
from app.api.research import router as research_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(analyze_router)
    app.include_router(health_router)
    app.include_router(portfolio_router)
    app.include_router(research_router)

    # Static UI Integration: Serve ARGUS UI if built static files exist
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        if (static_dir / "_next").exists():
            app.mount("/_next", StaticFiles(directory=str(static_dir / "_next")), name="next_static")

        @app.get("/", include_in_schema=False)
        async def serve_home():
            return FileResponse(str(static_dir / "index.html"))

        @app.get("/analyze", include_in_schema=False)
        @app.get("/analyze/", include_in_schema=False)
        async def serve_analyze():
            return FileResponse(str(static_dir / "analyze" / "index.html"))

        @app.get("/portfolio", include_in_schema=False)
        @app.get("/portfolio/", include_in_schema=False)
        async def serve_portfolio():
            return FileResponse(str(static_dir / "portfolio" / "index.html"))

        @app.get("/research", include_in_schema=False)
        @app.get("/research/", include_in_schema=False)
        async def serve_research():
            return FileResponse(str(static_dir / "research" / "index.html"))
    else:
        @app.get("/", include_in_schema=False)
        def root():
            """Redirect the root URL to the API documentation when UI is not built."""
            return RedirectResponse(url="/docs")

    return app


app = create_app()
