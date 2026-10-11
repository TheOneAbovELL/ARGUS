"""Typed application errors and the stable HTTP error envelope.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "details": ...}, "request_id": "..."}

Domain and service code raise subclasses of :class:`ArgusError`; route handlers
do not translate exceptions themselves. Messages are written for end users and
must never include secrets, stack traces, or raw upstream payloads.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id

logger = logging.getLogger("argus.errors")


class ArgusError(Exception):
    """Base class for errors that map to a deliberate HTTP response."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class InvalidRequestError(ArgusError):
    status_code = 400
    code = "invalid_request"


class NotFoundError(ArgusError):
    status_code = 404
    code = "not_found"


class SymbolNotFoundError(NotFoundError):
    code = "symbol_not_found"


class InsufficientDataError(ArgusError):
    """Valid request, but the available history cannot support the analysis."""

    status_code = 422
    code = "insufficient_data"


class ConflictError(ArgusError):
    status_code = 409
    code = "conflict"


class AuthenticationError(ArgusError):
    status_code = 401
    code = "authentication_required"


class PermissionDeniedError(ArgusError):
    status_code = 403
    code = "permission_denied"


class PayloadTooLargeError(ArgusError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaTypeError(ArgusError):
    status_code = 415
    code = "unsupported_media_type"


class RateLimitedError(ArgusError):
    status_code = 429
    code = "rate_limited"

    def __init__(
        self, message: str, *, retry_after: int | None = None, details: Any = None
    ) -> None:
        super().__init__(message, details=details)
        self.retry_after = retry_after


class ProviderError(ArgusError):
    """An upstream data provider failed (distinct from a valid empty result)."""

    status_code = 503
    code = "provider_unavailable"


class ProviderUnavailableError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    status_code = 504
    code = "provider_timeout"


class ProviderRateLimitedError(ProviderError):
    status_code = 503
    code = "provider_rate_limited"


class ModelUnavailableError(ArgusError):
    status_code = 503
    code = "model_unavailable"


class DependencyUnavailableError(ArgusError):
    status_code = 503
    code = "dependency_unavailable"


def error_body(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error, "request_id": get_request_id()}


def _response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_body(code, message, details),
        headers=headers,
    )


async def _argus_error_handler(_: Request, exc: ArgusError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.warning(
            "request failed",
            extra={"error_code": exc.code, "cause": repr(exc.__cause__)},
        )
    headers = None
    if isinstance(exc, RateLimitedError) and exc.retry_after:
        headers = {"Retry-After": str(exc.retry_after)}
    return _response(exc.status_code, exc.code, exc.message, exc.details, headers)


async def _validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "location": [str(part) for part in error.get("loc", ())],
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type"),
        }
        for error in exc.errors()
    ]
    first = details[0]["message"] if details else "Invalid request."
    return _response(422, "validation_error", first, details)


async def _http_error_handler(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = {
        404: "not_found",
        405: "method_not_allowed",
        401: "authentication_required",
        403: "permission_denied",
    }.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _response(exc.status_code, code, message, headers=exc.headers)


async def _database_error_handler(_: Request, exc: OperationalError) -> JSONResponse:
    logger.error("database operation failed", extra={"cause": type(exc).__name__})
    return _response(
        503,
        "database_unavailable",
        "The database is temporarily unavailable. Please try again shortly.",
    )


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)
    return _response(
        500,
        "internal_error",
        "An unexpected error occurred. Reference the request id when reporting it.",
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ArgusError, _argus_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(OperationalError, _database_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_error_handler)
