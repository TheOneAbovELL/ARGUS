"""ASGI middleware: request correlation, access logs, size limits, headers,
and the last-resort error boundary."""

import json
import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body
from app.core.logging import reset_request_id, set_request_id

logger = logging.getLogger("argus.access")
error_logger = logging.getLogger("argus.errors")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"x-frame-options", b"DENY"),
]


class _BodyTooLarge(Exception):
    pass


class RequestContextMiddleware:
    """Per request: assign a request id, enforce body-size limits on the bytes
    actually received (declared Content-Length *and* chunked bodies), add
    security headers, emit an access log line, and turn any exception that
    escapes the app into the standard error envelope (with the request id).

    Upload routes get their own, larger limit via ``upload_paths``."""

    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int,
        max_upload_bytes: int,
        upload_paths: tuple[str, ...] = (),
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.max_upload_bytes = max_upload_bytes
        self.upload_paths = upload_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        incoming = headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else uuid.uuid4().hex
        token = set_request_id(request_id)
        started = time.perf_counter()
        state = {"status": 500, "started": False, "too_large": False}
        limit = (
            self.max_upload_bytes
            if scope["path"] in self.upload_paths
            else self.max_body_bytes
        )
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Frameworks may catch this while parsing and answer 400;
                    # the flag makes send_wrapper replace that with a 413.
                    state["too_large"] = True
                    raise _BodyTooLarge
            return message

        async def emit(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                state["started"] = True
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode()))
                raw_headers.extend(_SECURITY_HEADERS)
                message["headers"] = raw_headers
            await send(message)

        async def send_wrapper(message: Message) -> None:
            if state["too_large"]:
                if message["type"] == "http.response.start" and not state["started"]:
                    await self._error(emit, 413, "payload_too_large", f"Request body exceeds the {limit:,} byte limit.")
                return  # drop the app's own response to the oversized request
            await emit(message)

        try:
            declared = headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > limit:
                await self._error(emit, 413, "payload_too_large", f"Request body exceeds the {limit:,} byte limit.")
                return
            await self.app(scope, limited_receive, send_wrapper)
        except _BodyTooLarge:
            if not state["started"]:
                await self._error(emit, 413, "payload_too_large", f"Request body exceeds the {limit:,} byte limit.")
        except Exception:
            error_logger.exception("unhandled error")
            if not state["started"]:
                await self._error(
                    emit,
                    500,
                    "internal_error",
                    "An unexpected error occurred. Reference the request id when reporting it.",
                )
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            path = scope.get("path", "")
            if not path.startswith("/_next"):
                logger.info(
                    "%s %s -> %s",
                    scope.get("method"),
                    path,
                    state["status"],
                    extra={"duration_ms": duration_ms},
                )
            reset_request_id(token)

    @staticmethod
    async def _error(send: Send, status: int, code: str, message: str) -> None:
        body = json.dumps(error_body(code, message)).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
