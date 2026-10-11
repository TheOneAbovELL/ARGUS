"""Security regression tests for findings from the release review.

Each test pins a control that an independent audit showed was missing or
bypassable: static-path handling (UNC paths on Windows), body-size limits by
exact route, credential endpoints that accept only JSON, password-spraying
limits, parser budgets, SEC download handling, and configuration guards.
"""

import asyncio
import io

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfWriter

from app.core.config import Settings
from app.core.errors import ConflictError, ProviderUnavailableError
from app.knowledge import document_loader
from app.knowledge.document_loader import DocumentLoader, DocumentLoadError, DocumentType
from app.main import _safe_relative_path, create_app
from app.providers.sec_edgar import SecEdgarClient
from tests.conftest import signup
from tests.test_sec_edgar import sec_client

# ── static file serving ───────────────────────────────────────────────


@pytest.mark.parametrize("path", [
    "\\\\attacker.invalid\\share\\x",
    "//attacker.invalid/share/x",
    "/etc/passwd",
    "../backend/.env",
    "asset/../../.env",
    "_next/../..",
    "C:/Windows/win.ini",
    "a//b",
    "x\x00y",
])
def test_unsafe_static_paths_are_rejected_before_touching_the_filesystem(path: str) -> None:
    assert _safe_relative_path(path) is False


@pytest.mark.parametrize("path", ["", "asset/", "asset/index.html", "_next/static/chunks/app.js", "404.html"])
def test_normal_static_paths_are_allowed(path: str) -> None:
    assert _safe_relative_path(path) is True


def test_static_catch_all_serves_pages_and_assets_and_404s_traversal(settings, container, tmp_path, monkeypatch) -> None:
    static = tmp_path / "static"
    (static / "asset").mkdir(parents=True)
    (static / "_next" / "static").mkdir(parents=True)
    (static / "index.html").write_text("<p>home</p>", encoding="utf-8")
    (static / "asset" / "index.html").write_text("<p>asset</p>", encoding="utf-8")
    (static / "404.html").write_text("<p>missing</p>", encoding="utf-8")
    (static / "_next" / "static" / "app.js").write_text("console.log(1)", encoding="utf-8")
    import app.main as main_module

    monkeypatch.setattr(main_module, "STATIC_DIR", static)
    with TestClient(create_app(settings, container)) as client:
        assert client.get("/").text == "<p>home</p>"
        assert client.get("/asset/").text == "<p>asset</p>"
        js = client.get("/_next/static/app.js")
        assert js.status_code == 200 and "immutable" in js.headers["cache-control"]
        for probe in ("/%5C%5Cattacker.invalid%5Cshare%5Cx", "/_next/%5C%5Cattacker%5Cx", "/..%2f..%2fbackend/.env", "/nope"):
            assert client.get(probe).status_code == 404, probe
        assert client.get("/api/does-not-exist").json()["error"]["code"] == "not_found"


# ── request limits and credential endpoints ───────────────────────────


def test_large_upload_limit_applies_only_to_the_upload_route(client: TestClient) -> None:
    signup(client)
    big = {"query": "x" * 2_000_000}
    response = client.post("/api/documents/search", json=big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_login_and_signup_require_json_content_type(client: TestClient) -> None:
    body = b'{"email":"a@example.com","password":"correct horse battery"}'
    for path in ("/api/auth/signup", "/api/auth/login"):
        for headers in ({}, {"Content-Type": "text/plain"}):
            response = client.post(path, content=body, headers=headers)
            assert response.status_code == 415, (path, headers, response.text)
            assert "set-cookie" not in response.headers


def test_password_spraying_across_emails_is_rate_limited_per_ip(client: TestClient) -> None:
    statuses = [
        client.post("/api/auth/login", json={"email": f"user{i}@example.com", "password": "wrong password!!"}).status_code
        for i in range(200)
    ]
    assert 429 in statuses
    assert statuses.index(429) <= 150  # 3x the per-minute auth budget (50 in tests)


def test_cors_wildcard_is_refused_with_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins=["*"], _env_file=None)


@pytest.mark.parametrize("rate", [4.5, -0.5, 1.0])
def test_risk_free_rate_must_be_an_annual_decimal(rate: float) -> None:
    with pytest.raises(ValidationError):
        Settings(quant_annual_risk_free_rate=rate, _env_file=None)


# ── parser budgets ─────────────────────────────────────────────────────


def test_html_text_cap_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(document_loader, "MAX_TEXT_CHARS", 1_000)
    html = "<html><body>" + "<p>word </p>" * 400 + "</body></html>"
    with pytest.raises(DocumentLoadError, match="too much text"):
        DocumentLoader().load_html(html, ticker="NVDA", document_type=DocumentType.OTHER, title="t", source="s")


def _pdf_with_content(stream: bytes, pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=200, height=200)
        from pypdf.generic import DecodedStreamObject, NameObject

        content = DecodedStreamObject()
        content.set_data(stream)
        page[NameObject("/Contents")] = writer._add_object(content)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_page_content_budget_rejects_amplification(monkeypatch) -> None:
    monkeypatch.setattr(document_loader, "MAX_PAGE_CONTENT_BYTES", 10_000)
    data = _pdf_with_content(b"0 0 m " * 5_000)  # ~30 KB of drawing operators, no text
    with pytest.raises(DocumentLoadError, match="too large or complex"):
        DocumentLoader().load_pdf_bytes(data, ticker="NVDA", document_type=DocumentType.OTHER, title="t", source="s")


def test_pdf_total_content_budget(monkeypatch) -> None:
    monkeypatch.setattr(document_loader, "MAX_PDF_CONTENT_BYTES", 20_000)
    data = _pdf_with_content(b"0 0 m " * 1_000, pages=5)  # 5 x 6 KB
    with pytest.raises(DocumentLoadError, match="too large or complex"):
        DocumentLoader().load_pdf_bytes(data, ticker="NVDA", document_type=DocumentType.OTHER, title="t", source="s")


# ── SEC EDGAR ──────────────────────────────────────────────────────────


def test_sec_redirect_is_an_error_not_a_filing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.example/"}, text="<html>not a filing</html>")

    client = SecEdgarClient("ARGUS tests ops@example.com", transport=httpx.MockTransport(handler), min_interval_seconds=0)
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(client._get("https://www.sec.gov/Archives/x.htm"))


def test_sec_download_is_capped_while_streaming() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 50_000)

    client = SecEdgarClient("ARGUS tests ops@example.com", transport=httpx.MockTransport(handler), min_interval_seconds=0)
    with pytest.raises(Exception, match="too large"):
        asyncio.run(client._get("https://www.sec.gov/Archives/x.htm", max_bytes=10_000))


def test_reimporting_a_filing_is_refused_before_downloading(authed: TestClient, container) -> None:
    requests: list[str] = []
    container.sec = sec_client(requests)
    body = {"symbol": "NVDA", "accession": "0001045810-26-000020"}
    assert authed.post("/api/documents/import-sec", json=body).status_code == 201
    downloads_before = sum(1 for r in requests if r.endswith(".htm"))
    again = authed.post("/api/documents/import-sec", json=body)
    assert again.status_code == ConflictError.status_code
    assert sum(1 for r in requests if r.endswith(".htm")) == downloads_before


def test_uploads_are_rate_limited_per_user(authed: TestClient, container) -> None:
    from app.core.rate_limit import SlidingWindowRateLimiter

    container.upload_limiter = SlidingWindowRateLimiter(2, 60)
    statuses = []
    for i in range(3):
        statuses.append(authed.post(
            "/api/documents", data={"symbol": "NVDA", "title": f"n{i}"},
            files={"file": ("note.txt", f"Supply chain risk {i}.".encode(), "text/plain")},
        ).status_code)
    assert statuses[:2] == [201, 201] and statuses[2] == 429
