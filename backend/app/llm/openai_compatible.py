"""Chat-completions provider for a *local* model server that exposes an
OpenAI-compatible endpoint (Ollama, LM Studio, llama.cpp, vLLM).

ARGUS's synthesis step can run against a free local model. To make accidental
spending impossible, non-local hosts are refused unless ``allow_remote`` is
explicitly enabled. Output is requested as a JSON Schema response format and
is validated by ARGUS afterwards regardless of what the server claims.
"""

import asyncio
import json
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.errors import ModelUnavailableError
from app.llm.base import LLMResult, ModelOutputError


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        max_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_remote: bool = False,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be an http(s) URL")
        if not allow_remote and not is_local_url(base_url):
            raise ValueError(
                "Only local model servers (localhost) are allowed. Set "
                "ARGUS_LLM_ALLOW_REMOTE=true to opt into a remote endpoint."
            )
        self.model = model
        # Host only (never the key): lets the UI say where prompts are sent.
        self.host = urlparse(base_url).hostname or ""
        self.is_local = is_local_url(base_url)
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._timeout = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._transport = transport

    async def generate_json(
        self, system: str, user: str, schema: dict[str, Any], max_output_tokens: int
    ) -> LLMResult:
        body = {
            "model": self.model,
            "max_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "research_report", "schema": schema, "strict": True},
            },
        }
        deadline = time.monotonic() + self._timeout
        last_error: Exception | None = None
        rate_limited = False
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            for attempt in range(self._max_attempts):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    response = await client.post(
                        self._url, json=body, headers=self._headers, timeout=remaining
                    )
                except httpx.HTTPError as exc:
                    last_error = exc
                    delay = 0.5 * (2**attempt)
                else:
                    if response.status_code == 429:
                        # Free tiers enforce per-minute token budgets; waiting for
                        # the advertised reset usually succeeds, retrying at once
                        # never does.
                        rate_limited = True
                        last_error = ModelUnavailableError("Model endpoint rate limited the request (HTTP 429).")
                        delay = retry_delay(response.headers) or 0.5 * (2**attempt)
                    elif response.status_code >= 500:
                        last_error = ModelUnavailableError(f"Model endpoint returned HTTP {response.status_code}.")
                        delay = 0.5 * (2**attempt)
                    elif response.status_code >= 400:
                        code = error_code(response)
                        if code == "json_validate_failed":
                            # The model produced JSON that failed the schema
                            # server-side: a generation failure, worth a retry.
                            # Retry in plain JSON mode with the schema in the
                            # prompt; ARGUS validates structure and every claim
                            # itself, so strict server-side enforcement is a
                            # convenience, not the safety boundary.
                            last_error = ModelOutputError("The model's output did not match the schema.")
                            body = json_object_body(body, schema)
                            delay = 0.5
                        else:
                            raise ModelOutputError(
                                f"Model endpoint rejected the request (HTTP {response.status_code}"
                                + (f": {code}" if code else "")
                                + ")."
                            )
                    else:
                        try:
                            payload = response.json()
                        except ValueError as exc:
                            raise ModelOutputError("The model endpoint returned a non-JSON response.") from exc
                        return self._parse(payload)
                if attempt + 1 >= self._max_attempts or delay >= deadline - time.monotonic():
                    break
                await asyncio.sleep(delay)
        if isinstance(last_error, ModelOutputError):
            raise last_error
        if rate_limited:
            raise ModelUnavailableError(
                "The language model's rate limit was reached; try again in a minute."
            ) from last_error
        raise ModelUnavailableError("The language model endpoint is unavailable.") from last_error

    def _parse(self, payload: dict[str, Any]) -> LLMResult:
        try:
            choice = payload["choices"][0]
            text = choice["message"]["content"]
            data = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ModelOutputError("The language model returned malformed JSON.") from exc
        if choice.get("finish_reason") == "length":
            raise ModelOutputError("The model's answer was truncated before completion.")
        if not isinstance(data, dict):
            raise ModelOutputError("The language model returned JSON that is not an object.")
        usage = payload.get("usage") or {}
        return LLMResult(
            data=data,
            model=payload.get("model", self.model),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            stop_reason=choice.get("finish_reason"),
        )


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def is_local_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in LOCAL_HOSTS or host.endswith(".localhost")


_DURATION = re.compile(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?$")


def retry_delay(headers: httpx.Headers, cap: float = 65.0) -> float | None:
    """Seconds to wait before retrying, from ``retry-after`` or the token-
    budget reset hint (e.g. ``x-ratelimit-reset-tokens: 26.625s`` or ``1m2s``)."""
    for name in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        value = (headers.get(name) or "").strip()
        if not value:
            continue
        try:
            seconds = float(value)
        except ValueError:
            match = _DURATION.match(value)
            if not match or not any(match.groups()):
                continue
            h, m, sec, ms = (float(g) if g else 0.0 for g in match.groups())
            seconds = h * 3600 + m * 60 + sec + ms / 1000
        return min(max(seconds, 0.0) + 0.25, cap)
    return None


def error_code(response: httpx.Response) -> str | None:
    """The provider's machine-readable error code, if any (never the body)."""
    try:
        error = response.json().get("error")
    except ValueError:
        return None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) and len(code) <= 64 else None


def json_object_body(body: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Same request in ``json_object`` mode, with the schema stated in the
    system message instead of enforced by the server."""
    messages = [dict(m) for m in body["messages"]]
    messages[0]["content"] += (
        "\n\nReturn only a JSON object that conforms to this JSON Schema:\n"
        + json.dumps(schema, separators=(",", ":"))
    )
    return {**body, "messages": messages, "response_format": {"type": "json_object"}}
