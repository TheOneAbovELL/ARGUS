"""Account and session routes."""

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import CSRF_HEADER, ContainerDep, CurrentUser, DbDep, extract_token, require_json
from app.core.errors import PermissionDeniedError
from app.schemas.workspace import LoginIn, SessionOut, SignupIn, UserOut
from app.services.auth import AuthService, IssuedSession

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, container, issued: IssuedSession) -> None:
    settings = container.settings
    response.set_cookie(
        settings.session_cookie_name,
        issued.token,
        max_age=int(container.session_ttl.total_seconds()),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _session_out(issued: IssuedSession, include_token: bool) -> SessionOut:
    return SessionOut(
        user=UserOut.of(issued.user),
        expires_at=issued.expires_at,
        token=issued.token if include_token else None,
    )


@router.post("/signup", response_model=SessionOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_json)])
async def signup(
    body: SignupIn,
    request: Request,
    response: Response,
    container: ContainerDep,
    db: DbDep,
    return_token: bool = Query(False, description="Include the bearer token for API clients"),
):
    container.auth_limiter.check(f"signup:{request.client.host if request.client else '-'}")
    issued = await AuthService(db, container.session_ttl).signup(
        body.email, body.password, body.display_name, request.headers.get("user-agent")
    )
    _set_cookie(response, container, issued)
    return _session_out(issued, return_token)


@router.post("/login", response_model=SessionOut, dependencies=[Depends(require_json)])
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    container: ContainerDep,
    db: DbDep,
    return_token: bool = Query(False),
):
    host = request.client.host if request.client else "-"
    # Per-IP budget across all emails (password spraying), then per account.
    container.login_ip_limiter.check(f"login-ip:{host}", "Too many sign-in attempts from this address. Please wait a minute.")
    container.auth_limiter.check(f"login:{host}:{body.email.strip().lower()}",
                                 "Too many sign-in attempts. Please wait a minute and try again.")
    issued = await AuthService(db, container.session_ttl).login(
        body.email, body.password, request.headers.get("user-agent")
    )
    _set_cookie(response, container, issued)
    return _session_out(issued, return_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, container: ContainerDep, db: DbDep) -> Response:
    token, from_cookie = extract_token(request, container.settings.session_cookie_name)
    if token and from_cookie and request.headers.get(CSRF_HEADER) != "1":
        raise PermissionDeniedError("Missing CSRF header for a cookie-authenticated request.")
    if token:
        await AuthService(db, container.session_ttl).logout(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(container.settings.session_cookie_name, path="/")
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return UserOut.of(user)
