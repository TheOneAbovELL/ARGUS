"""FastAPI application factory for ARGUS.

The JSON API lives under ``/api`` (plus ``/health`` probes) so it never
collides with the single-page app's client routes, which this process also
serves when a static frontend build is present in ``app/static``.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from app.api import auth, market, portfolio, research, system, workspace
from app.core.config import Settings, get_settings
from app.core.container import Container
from app.core.errors import NotFoundError, install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import run_migrations

logger = logging.getLogger("argus.app")
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    settings: Settings | None = None,
    container: Container | None = None,
    run_db_migrations: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active = container or Container(settings)
        if run_db_migrations and settings.auto_migrate:
            # Alembic migrations, not create_all: the same path production uses.
            await asyncio.to_thread(run_migrations, active.database.url)
        app.state.container = active
        if active.embedding_prefetcher is not None:
            active.embedding_prefetcher.start_background()  # no-op when present
        logger.info(
            "ARGUS started",
            extra={
                "market_data": active.provider.name,
                "research_mode": "llm" if active.llm else "deterministic",
            },
        )
        if settings.environment == "production" and not settings.session_cookie_secure:
            logger.warning(
                "session cookies are not marked Secure; set ARGUS_SESSION_COOKIE_SECURE=true when serving over HTTPS"
            )
        try:
            yield
        finally:
            await active.database.dispose()

    docs = settings.expose_api_docs if settings.expose_api_docs is not None else settings.environment != "production"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        description=(
            "AI-assisted quantitative research API. Metrics are computed deterministically; "
            "every research claim cites verifiable evidence. Not investment advice."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-ARGUS-CSRF", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(
        RequestContextMiddleware,
        max_body_bytes=settings.max_request_bytes,
        max_upload_bytes=settings.max_upload_bytes + 64_000,  # multipart framing overhead
        upload_paths=("/api/documents",),  # exact path: only the multipart upload route
    )
    install_error_handlers(app)

    for module in (system, auth, market, portfolio, research, workspace):
        app.include_router(module.router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the exported Next.js app when it has been built into app/static.

    Each route is a pre-rendered ``<route>/index.html``; unknown non-API paths
    get the exported 404 page. Path resolution is confined to STATIC_DIR."""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        @app.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse(url="/docs")

        return

    root_dir = STATIC_DIR.resolve()

    # One handler serves pages and hashed /_next assets. The URL path is
    # validated as a plain relative POSIX path *before* any filesystem call:
    # on Windows, resolving "\\host\share" would open a UNC path (SMB/NTLM
    # leak) and block the event loop. No symlinks exist in the export, so no
    # resolve() is needed once the segments are known to be safe.
    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith(("api/", "health")) or not _safe_relative_path(path):
            raise NotFoundError("Not found.")
        candidate = root_dir.joinpath(*PurePosixPath(path).parts) if path else root_dir
        if candidate.is_file():
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if path.startswith("_next/static/") else None
            return FileResponse(candidate, headers=headers)
        page = candidate / "index.html"
        if page.is_file():
            return FileResponse(page)
        not_found = root_dir / "404.html"
        return FileResponse(not_found if not_found.exists() else index, status_code=404)


def _safe_relative_path(path: str) -> bool:
    """A URL path segment list that can only name a file inside the static dir."""
    if not path:
        return True
    if any(ch in path for ch in ("\\", ":", "\x00")) or path.startswith("/"):
        return False
    return all(part not in ("", ".", "..") for part in path.rstrip("/").split("/"))


app = create_app()
