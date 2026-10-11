"""OpenAI-compatible provider: safety guard, rate limits, malformed output (offline)."""

import asyncio
import json
import time

import httpx
import pytest

from app.core.errors import ModelUnavailableError
from app.llm.base import ModelOutputError
from app.llm.openai_compatible import OpenAICompatibleProvider, is_local_url, retry_delay

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}


def completion(content: str, finish: str = "stop") -> dict:
    return {"model": "m", "choices": [{"message": {"content": content}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def provider(handler, **kwargs) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider("m", "http://localhost:11434/v1", transport=httpx.MockTransport(handler), **kwargs)


def test_remote_endpoints_are_refused_unless_explicitly_allowed() -> None:
    assert is_local_url("http://localhost:11434/v1") and is_local_url("http://127.0.0.1:1234")
    assert not is_local_url("https://api.example.com/v1")
    with pytest.raises(ValueError):
        OpenAICompatibleProvider("m", "https://api.example.com/v1")
    OpenAICompatibleProvider("m", "https://api.example.com/v1", allow_remote=True)  # opt-in works


def test_successful_structured_response() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=completion('{"ok": true}'))

    result = asyncio.run(provider(handler).generate_json("sys", "user", SCHEMA, 100))
    assert result.data == {"ok": True} and result.input_tokens == 10
    assert seen["response_format"]["json_schema"]["schema"] == SCHEMA


def test_rate_limit_waits_for_advertised_reset_then_succeeds() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(time.monotonic())
        if len(calls) == 1:
            return httpx.Response(429, headers={"x-ratelimit-reset-tokens": "0.2s"})
        return httpx.Response(200, json=completion('{"ok": true}'))

    result = asyncio.run(provider(handler, max_attempts=2).generate_json("s", "u", SCHEMA, 50))
    assert result.data == {"ok": True}
    assert calls[1] - calls[0] >= 0.2


def test_rate_limit_beyond_budget_reports_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "30"})

    with pytest.raises(ModelUnavailableError, match="rate limit"):
        asyncio.run(provider(handler, timeout_seconds=1, max_attempts=3).generate_json("s", "u", SCHEMA, 50))


@pytest.mark.parametrize("payload,match", [
    (completion("not json"), "malformed"),
    (completion('{"ok": true'), "malformed"),
    (completion('{"ok": true}', finish="length"), "truncated"),
    ({"unexpected": 1}, "malformed"),
])
def test_unusable_output_is_a_model_output_error(payload, match) -> None:
    with pytest.raises(ModelOutputError, match=match):
        asyncio.run(provider(lambda r: httpx.Response(200, json=payload)).generate_json("s", "u", SCHEMA, 50))


def test_client_errors_are_not_retried() -> None:
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"error": "bad"})

    with pytest.raises(ModelOutputError):
        asyncio.run(provider(handler, max_attempts=3).generate_json("s", "u", SCHEMA, 50))
    assert len(calls) == 1


@pytest.mark.parametrize("headers,expected", [
    ({"retry-after": "7"}, 7.25),
    ({"x-ratelimit-reset-tokens": "26.625s"}, 26.875),
    ({"x-ratelimit-reset-tokens": "1m2s"}, 62.25),
    ({"x-ratelimit-reset-tokens": "450ms"}, 0.7),
    ({"x-ratelimit-reset-requests": "7m12s"}, 65.0),  # capped
    ({}, None),
])
def test_retry_delay_parsing(headers, expected) -> None:
    assert retry_delay(httpx.Headers(headers)) == pytest.approx(expected) if expected else retry_delay(httpx.Headers(headers)) is None


def test_non_json_success_body_is_a_model_output_error() -> None:
    with pytest.raises(ModelOutputError, match="non-JSON"):
        asyncio.run(provider(lambda r: httpx.Response(200, text="<html>gateway</html>")).generate_json("s", "u", SCHEMA, 50))


def test_schema_validation_failure_is_retried_once() -> None:
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(400, json={"error": {"code": "json_validate_failed", "message": "Failed to generate JSON"}})
        return httpx.Response(200, json=completion('{"ok": true}'))

    assert asyncio.run(provider(handler, max_attempts=2).generate_json("s", "u", SCHEMA, 50)).data == {"ok": True}


def test_persistent_schema_failure_is_reported_as_output_error() -> None:
    def handler(request):
        return httpx.Response(400, json={"error": {"code": "json_validate_failed"}})

    with pytest.raises(ModelOutputError, match="did not match the schema"):
        asyncio.run(provider(handler, max_attempts=2).generate_json("s", "u", SCHEMA, 50))


def test_other_client_errors_include_only_the_error_code() -> None:
    def handler(request):
        return httpx.Response(400, json={"error": {"code": "model_decommissioned", "message": "secret detail"}})

    with pytest.raises(ModelOutputError) as info:
        asyncio.run(provider(handler).generate_json("s", "u", SCHEMA, 50))
    assert "model_decommissioned" in info.value.message and "secret detail" not in info.value.message


def test_repeated_schema_failure_falls_back_to_json_object_mode() -> None:
    modes = []

    def handler(request):
        body = json.loads(request.content)
        modes.append(body["response_format"]["type"])
        if body["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": {"code": "json_validate_failed"}})
        assert "conforms to this JSON Schema" in body["messages"][0]["content"]
        return httpx.Response(200, json=completion('{"ok": true}'))

    result = asyncio.run(provider(handler, max_attempts=3).generate_json("s", "u", SCHEMA, 50))
    assert result.data == {"ok": True} and modes == ["json_schema", "json_object"]


def test_provider_exposes_host_and_locality_but_not_the_key():
    remote = OpenAICompatibleProvider(
        model="m", base_url="https://api.groq.com/openai/v1", api_key="secret-key", allow_remote=True
    )
    assert remote.host == "api.groq.com"
    assert remote.is_local is False
    assert "secret-key" not in (remote.host + str(remote.is_local))
    local = OpenAICompatibleProvider(model="m", base_url="http://127.0.0.1:11434/v1")
    assert local.host == "127.0.0.1"
    assert local.is_local is True
