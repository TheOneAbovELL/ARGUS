"""FastAPI dependencies: container access, DB sessions, and authentication.

Authentication accepts either the ``argus_session`` HttpOnly cookie (browser)
or an ``Authorization: Bearer`` token (API clients). Cookie-authenticated
state-changing requests must also send ``X-ARGUS-CSRF: 1``: a custom header
cannot be attached by a cross-site form, and cross-origin scripts need a CORS
preflight that only allow-listed origins pass. Together with
``SameSite=Lax`` this blocks CSRF without a token round-trip.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import Container
from app.core.errors import AuthenticationError, PermissionDeniedError, UnsupportedMediaTypeError
from app.db.models import User
from app.services.auth import AuthService

CSRF_HEADER = "x-argus-csrf"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_db(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async for session in container.database.session():
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]


def extract_token(request: Request, cookie_name: str) -> tuple[str | None, bool]:
    """Return (token, came_from_cookie)."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        return (token or None), False
    cookie = request.cookies.get(cookie_name)
    return (cookie or None), cookie is not None


async def optional_user(request: Request, container: ContainerDep, db: DbDep) -> User | None:
    token, from_cookie = extract_token(request, container.settings.session_cookie_name)
    if not token:
        return None
    user = await AuthService(db, container.session_ttl).resolve(token)
    if user is None:
        return None
    if from_cookie and request.method not in _SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise PermissionDeniedError("Missing CSRF header for a cookie-authenticated request.")
    return user


async def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise AuthenticationError("Sign in to use this feature.")
    return user


OptionalUser = Annotated[User | None, Depends(optional_user)]
CurrentUser = Annotated[User, Depends(current_user)]


async def provider_rate_limit(request: Request, container: ContainerDep) -> None:
    """Per-client budget for routes that call external data providers."""
    container.api_limiter.check(client_key(request), "Too many market-data requests; please slow down.")


async def require_json(request: Request) -> None:
    """Credential endpoints accept only application/json bodies, so a
    cross-site "simple" request (form or type-less fetch) cannot reach them
    without a CORS preflight."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise UnsupportedMediaTypeError("Send the request body as application/json.")


def client_key(request: Request, user: User | None = None) -> str:
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{request.client.host if request.client else 'unknown'}"
