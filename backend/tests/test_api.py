"""HTTP-level integration tests: contracts, auth, ownership, and workflows."""

import json

import pytest
from fastapi.testclient import TestClient

from tests.conftest import signup


def error_code(response) -> str:
    body = response.json()
    assert set(body) >= {"error", "request_id"}, body
    return body["error"]["code"]


# ── system ────────────────────────────────────────────────────────────


def test_health_ready_status_and_request_ids(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["checks"]["database"] == "ok"
    status = client.get("/api/system/status").json()
    assert status["market_data"]["mode"] == "fixture"
    assert status["research"]["mode"] == "deterministic"
    response = client.get("/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert response.headers["x-request-id"] == "trace-abc-12345"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_metric_definitions_cover_reported_metrics(client: TestClient) -> None:
    keys = {d["key"] for d in client.get("/api/meta/metrics").json()}
    assert {"sharpe_ratio", "sortino_ratio", "var_95", "beta", "risk_contribution"} <= keys


def test_openapi_schema_is_generated(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/api/analytics/asset", "/api/portfolio/analyze", "/api/research", "/api/documents", "/api/auth/login"):
        assert path in paths


def test_unknown_api_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404 and error_code(response) == "not_found"


def test_oversized_body_is_rejected_before_parsing(client: TestClient) -> None:
    response = client.post("/api/research", content=b"x" * 2_000_000, headers={"Content-Type": "application/json"})
    assert response.status_code == 413 and error_code(response) == "payload_too_large"


# ── market & analytics ────────────────────────────────────────────────


def test_market_endpoints_return_provenance(client: TestClient) -> None:
    quote = client.get("/api/market/aapl/quote").json()
    assert quote["symbol"] == "AAPL" and quote["provenance"]["mode"] == "fixture"
    history = client.get("/api/market/AAPL/history", params={"period": "3mo"}).json()
    assert len(history["dates"]) == len(history["close"]) == len(history["adj_close"]) > 50
    assert client.get("/api/market/search", params={"q": "micro"}).json()[0]["symbol"] == "MSFT"
    batch = client.get("/api/market/quotes", params={"symbols": "SPY,NOPE"}).json()
    assert batch[0]["quote"] and batch[1]["quote"] is None and batch[1]["error"]
    assert client.get("/api/market/NVDA/profile").json()["sector"] == "Technology"
    assert client.get("/api/market/NVDA/news").json()["items"]


def test_asset_analysis_contract(client: TestClient) -> None:
    body = client.post("/api/analytics/asset", json={"symbol": "NVDA", "period": "2y", "benchmark": "QQQ"}).json()
    assert body["benchmark"] == "QQQ" and body["window"]["label"] == "2y"
    perf = body["performance"]
    assert perf["max_drawdown"] <= 0 and perf["var_95"] < 0 and perf["cvar_95"] <= perf["var_95"]
    assert -1 <= body["relative"]["correlation"] <= 1
    series = body["series"]
    assert len(series["dates"]) == len(series["drawdown"]) == len(series["rolling_volatility"])
    assert series["rolling_volatility"][0] is None
    assert set(body["provenance"]) == {"NVDA", "QQQ"}


@pytest.mark.parametrize("payload,status,code", [
    ({"symbol": "NOPE"}, 404, "symbol_not_found"),
    ({"symbol": "NVDA!"}, 400, "invalid_request"),
    ({"symbol": "NVDA", "period": "7y"}, 400, "invalid_request"),
    ({"symbol": "NVDA", "risk_free_rate": 5}, 422, "validation_error"),
    ({"symbol": "NVDA", "start": "2026-06-29", "end": "2026-06-30"}, 422, "insufficient_data"),
])
def test_asset_analysis_errors_are_distinct(client: TestClient, payload, status, code) -> None:
    response = client.post("/api/analytics/asset", json=payload)
    assert response.status_code == status and error_code(response) == code


# ── portfolio analytics ───────────────────────────────────────────────


def test_portfolio_analysis_and_stress(client: TestClient) -> None:
    holdings = [{"symbol": "AAPL", "weight": 50}, {"symbol": "TLT", "weight": 30}, {"symbol": "GLD", "weight": 20}]
    body = client.post("/api/portfolio/analyze", json={"holdings": holdings, "model": "buy_and_hold", "period": "3y"}).json()
    assert body["model"] == "buy_and_hold"
    assert sum(a["risk_contribution"] for a in body["assets"]) == pytest.approx(1.0)
    assert sum(a["return_contribution"] for a in body["assets"]) == pytest.approx(body["performance"]["total_return"])
    assert len(body["correlation"]) == 3 and body["assumptions"]
    stress = client.post("/api/portfolio/stress", json={"holdings": holdings}).json()
    covid = next(e for e in stress["episodes"] if e["key"] == "covid")
    assert covid["computable"] and covid["portfolio_return"] is not None


@pytest.mark.parametrize("holdings", [
    [{"symbol": "AAPL", "weight": 60}],
    [{"symbol": "AAPL", "weight": 50}, {"symbol": "aapl", "weight": 50}],
    [{"symbol": "AAPL", "weight": 0}, {"symbol": "TLT", "weight": 100}],
])
def test_portfolio_validation(client: TestClient, holdings) -> None:
    response = client.post("/api/portfolio/analyze", json={"holdings": holdings})
    assert response.status_code == 422 and error_code(response) == "validation_error"


def test_portfolio_with_unknown_symbol_names_it(client: TestClient) -> None:
    response = client.post("/api/portfolio/analyze", json={"holdings": [{"symbol": "AAPL", "weight": 50}, {"symbol": "NOPE", "weight": 50}]})
    assert response.status_code == 404 and response.json()["error"]["details"]["symbols"] == ["NOPE"]


# ── authentication ────────────────────────────────────────────────────


def test_signup_login_me_logout_cycle(client: TestClient) -> None:
    created = signup(client)
    assert created["user"]["email"] == "analyst@example.com" and created["token"] is None
    assert "argus_session" in client.cookies
    assert client.get("/api/auth/me").json()["email"] == "analyst@example.com"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    login = client.post("/api/auth/login", json={"email": "ANALYST@example.com ", "password": "correct horse battery"})
    assert login.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_auth_rejections(client: TestClient) -> None:
    signup(client)
    duplicate = client.post("/api/auth/signup", json={"email": "analyst@example.com", "password": "another long pw"})
    assert duplicate.status_code == 409
    wrong = client.post("/api/auth/login", json={"email": "analyst@example.com", "password": "wrong password!"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong password!"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]  # no user enumeration
    short = client.post("/api/auth/signup", json={"email": "x@example.com", "password": "short"})
    assert short.status_code == 400


def test_bearer_tokens_work_for_api_clients(client: TestClient) -> None:
    token = client.post("/api/auth/signup", params={"return_token": True},
                        json={"email": "bot@example.com", "password": "a very long password"}).json()["token"]
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    # bearer requests are not CSRF-exposed, so no custom header is required
    assert client.post("/api/watchlist", json={"symbol": "SPY"}, headers=headers).status_code == 201
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_cookie_mutations_require_csrf_header(client: TestClient) -> None:
    signup(client)
    del client.headers["X-ARGUS-CSRF"]
    response = client.post("/api/watchlist", json={"symbol": "SPY"})
    assert response.status_code == 403 and error_code(response) == "permission_denied"
    assert client.get("/api/watchlist").status_code == 200  # safe methods are fine


def test_login_is_rate_limited(client: TestClient, container) -> None:
    container.auth_limiter._limit = 3
    for _ in range(3):
        client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong password!"})
    response = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong password!"})
    assert response.status_code == 429 and response.headers["retry-after"]


def test_protected_routes_require_auth(client: TestClient) -> None:
    for method, path in [("get", "/api/portfolios"), ("get", "/api/watchlist"), ("get", "/api/research"),
                         ("get", "/api/documents"), ("post", "/api/documents/search")]:
        response = getattr(client, method)(path) if method == "get" else client.post(path, json={"query": "x"})
        assert response.status_code == 401, path


# ── saved portfolios, watchlist, ownership ────────────────────────────


PORTFOLIO = {"name": "Core", "benchmark": "spy", "rebalancing": "buy_and_hold",
             "holdings": [{"symbol": "AAPL", "weight": 70}, {"symbol": "TLT", "weight": 30}]}


def test_portfolio_crud_with_optimistic_concurrency(authed: TestClient) -> None:
    created = authed.post("/api/portfolios", json=PORTFOLIO).json()
    assert created["benchmark"] == "SPY" and created["holdings"][0] == {"symbol": "AAPL", "weight": 70.0}
    assert authed.post("/api/portfolios", json=PORTFOLIO).status_code == 409  # duplicate name

    update = {**PORTFOLIO, "name": "Core v2", "version": created["version"],
              "holdings": [{"symbol": "MSFT", "weight": 100}]}
    updated = authed.put(f"/api/portfolios/{created['id']}", json=update).json()
    assert updated["version"] == created["version"] + 1 and updated["holdings"] == [{"symbol": "MSFT", "weight": 100.0}]
    stale = authed.put(f"/api/portfolios/{created['id']}", json=update)
    assert stale.status_code == 409 and stale.json()["error"]["details"]["current_version"] == updated["version"]

    listing = authed.get("/api/portfolios").json()
    assert listing["page"]["total"] == 1
    assert authed.delete(f"/api/portfolios/{created['id']}").status_code == 204
    assert authed.get(f"/api/portfolios/{created['id']}").status_code == 404


def test_users_cannot_see_or_touch_each_others_data(client: TestClient) -> None:
    signup(client, "alice@example.com")
    portfolio = client.post("/api/portfolios", json=PORTFOLIO).json()
    client.post("/api/watchlist", json={"symbol": "NVDA"})
    report = client.post("/api/research", json={"symbol": "NVDA"}).json()
    client.post("/api/auth/logout")

    signup(client, "mallory@example.com")
    assert client.get(f"/api/portfolios/{portfolio['id']}").status_code == 404
    assert client.put(f"/api/portfolios/{portfolio['id']}", json={**PORTFOLIO, "version": 1}).status_code == 404
    assert client.delete(f"/api/portfolios/{portfolio['id']}").status_code == 404
    assert client.get(f"/api/research/{report['id']}").status_code == 404
    assert client.delete(f"/api/research/{report['id']}").status_code == 404
    assert client.get("/api/portfolios").json()["items"] == []
    assert client.get("/api/watchlist").json() == []
    assert client.get("/api/research").json()["items"] == []


def test_watchlist_is_idempotent(authed: TestClient) -> None:
    assert authed.post("/api/watchlist", json={"symbol": "spy"}).status_code == 201
    assert authed.post("/api/watchlist", json={"symbol": "SPY"}).status_code == 201
    assert [i["symbol"] for i in authed.get("/api/watchlist").json()] == ["SPY"]
    assert authed.delete("/api/watchlist/SPY").status_code == 204
    assert authed.delete("/api/watchlist/SPY").status_code == 404


# ── research ──────────────────────────────────────────────────────────


def test_anonymous_research_is_not_saved(client: TestClient) -> None:
    body = client.post("/api/research", json={"symbol": "NVDA", "question": "What drives risk?"}).json()
    assert body["saved"] is False and body["id"] is None
    assert body["generation"]["validation"]["claims_rejected"] == 0
    assert any("Sign in" in note for note in body["limitations"])


def test_research_history_persists_reports(authed: TestClient) -> None:
    report = authed.post("/api/research", json={"symbol": "MSFT", "question": "Volatility?"}).json()
    assert report["saved"] and report["id"]
    listing = authed.get("/api/research").json()
    assert listing["items"][0]["id"] == report["id"] and listing["items"][0]["claims"] > 0
    reloaded = authed.get(f"/api/research/{report['id']}").json()
    assert reloaded["sections"] == report["sections"] and reloaded["evidence"] == report["evidence"]
    assert authed.get("/api/research", params={"symbol": "AAPL"}).json()["items"] == []
    assert authed.delete(f"/api/research/{report['id']}").status_code == 204


def test_research_stream_emits_steps_then_report(client: TestClient) -> None:
    with client.stream("POST", "/api/research/stream", json={"symbol": "NVDA"}) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = "".join(response.iter_text())
    events = [block for block in raw.strip().split("\n\n") if block]
    names = [block.split("\n")[0].removeprefix("event: ") for block in events]
    assert names[0] == "step" and names[-1] == "report"
    report = json.loads(events[-1].split("data: ", 1)[1])
    assert report["symbol"] == "NVDA"


def test_research_stream_reports_errors_as_events(client: TestClient) -> None:
    with client.stream("POST", "/api/research/stream", json={"symbol": "NOPE"}) as response:
        raw = "".join(response.iter_text())
    assert "event: error" in raw and "symbol_not_found" in raw


def test_research_rate_limit(client: TestClient, container) -> None:
    container.research_limiter._limit = 1
    assert client.post("/api/research", json={"symbol": "NVDA"}).status_code == 200
    assert client.post("/api/research", json={"symbol": "NVDA"}).status_code == 429


# ── documents ─────────────────────────────────────────────────────────


FILING = (
    b"Item 1A. Risk Factors. Our supply chain depends on a limited number of foundry partners in Taiwan. "
    b"Export controls on advanced chips could reduce data center revenue. "
    b"Management expects gross margin to remain stable next quarter."
)


def upload(client: TestClient, name="10k.txt", data=FILING, symbol="NVDA", **form):
    return client.post(
        "/api/documents",
        files={"file": (name, data, "text/plain")},
        data={"symbol": symbol, "document_type": "10-K", **form},
    )


def minimal_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_document_lifecycle_upload_search_cite_delete(authed: TestClient) -> None:
    created = upload(authed, title="NVIDIA 10-K", published_on="2026-02-20")
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["status"] == "ready" and document["chunk_count"] >= 1 and document["published_on"] == "2026-02-20"

    assert upload(authed).status_code == 409  # same bytes twice
    found = authed.post("/api/documents/search", json={"query": "foundry supply chain Taiwan", "symbol": "NVDA"}).json()
    assert not found["insufficient_evidence"] and found["passages"][0]["document_id"] == document["id"]

    report = authed.post("/api/research", json={"symbol": "NVDA", "question": "What are the supply chain risks?"}).json()
    doc_evidence = [e for e in report["evidence"] if e["kind"] == "document"]
    assert doc_evidence and doc_evidence[0]["document_id"] == document["id"]
    answer = next(s for s in report["sections"] if s["key"] == "answer")
    assert answer["claims"]

    file = authed.get(f"/api/documents/{document['id']}/file")
    assert file.status_code == 200 and file.content == FILING
    assert file.headers["content-security-policy"] == "sandbox"

    assert authed.delete(f"/api/documents/{document['id']}").status_code == 204
    after = authed.post("/api/documents/search", json={"query": "foundry supply chain Taiwan"}).json()
    assert after["insufficient_evidence"] is True
    assert authed.get(f"/api/documents/{document['id']}/file").status_code == 404


def test_pdf_upload_extracts_page_text(authed: TestClient) -> None:
    response = authed.post(
        "/api/documents",
        files={"file": ("q.pdf", minimal_pdf("Quarterly revenue grew on data center demand"), "application/pdf")},
        data={"symbol": "NVDA", "document_type": "10-Q"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["page_count"] == 1


@pytest.mark.parametrize("name,data,status,code", [
    ("scan.pdf", minimal_pdf(""), 422, "document_unreadable"),
    ("fake.pdf", b"not really a pdf", 415, "unsupported_media_type"),
    ("image.png", b"\x89PNG\r\n", 415, "unsupported_media_type"),
    ("empty.txt", b"", 400, "invalid_request"),
    ("blank.txt", b"   \n  ", 422, "document_unreadable"),
])
def test_bad_uploads_are_rejected_without_leaving_records(authed: TestClient, name, data, status, code) -> None:
    response = authed.post("/api/documents", files={"file": (name, data, "application/octet-stream")},
                           data={"symbol": "NVDA"})
    assert response.status_code == status and error_code(response) == code
    assert authed.get("/api/documents").json()["page"]["total"] == 0


def test_upload_size_limit_is_enforced_while_streaming(authed: TestClient, container) -> None:
    container.settings.max_upload_bytes = 100
    response = upload(authed, data=b"a" * 500)
    assert response.status_code == 413


def test_documents_are_private(client: TestClient) -> None:
    signup(client, "alice@example.com")
    document = upload(client).json()
    client.post("/api/auth/logout")
    signup(client, "mallory@example.com")
    assert client.get(f"/api/documents/{document['id']}").status_code == 404
    assert client.get(f"/api/documents/{document['id']}/file").status_code == 404
    assert client.delete(f"/api/documents/{document['id']}").status_code == 404
    search = client.post("/api/documents/search", json={"query": "foundry supply chain Taiwan"}).json()
    assert search["passages"] == []
    report = client.post("/api/research", json={"symbol": "NVDA", "question": "supply chain"}).json()
    assert not [e for e in report["evidence"] if e["kind"] == "document"]


def test_chunked_bodies_cannot_bypass_the_size_limit(client: TestClient) -> None:
    def chunks():
        for _ in range(40):
            yield b"x" * 50_000  # 2 MB total, no Content-Length header

    response = client.post("/api/research", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413 and error_code(response) == "payload_too_large"


def test_unexpected_errors_keep_request_id_and_headers(client: TestClient, container) -> None:
    async def boom(*args, **kwargs):
        raise RuntimeError("db password=hunter2 at /srv/secret.py")

    container.analytics.analyze_asset = boom
    response = client.post("/api/analytics/asset", json={"symbol": "NVDA"}, headers={"X-Request-ID": "req-boom-12345"})
    assert response.status_code == 500
    assert response.json()["request_id"] == "req-boom-12345"
    assert response.json()["error"]["code"] == "internal_error" and "hunter2" not in response.text
    assert response.headers["x-request-id"] == "req-boom-12345"


def test_renaming_to_an_existing_name_is_a_conflict_not_a_500(authed: TestClient) -> None:
    first = authed.post("/api/portfolios", json=PORTFOLIO).json()
    second = authed.post("/api/portfolios", json={**PORTFOLIO, "name": "Other"}).json()
    response = authed.put(f"/api/portfolios/{second['id']}", json={**PORTFOLIO, "name": first["name"], "version": second["version"]})
    assert response.status_code == 409 and error_code(response) == "conflict"
    assert authed.get(f"/api/portfolios/{second['id']}").json()["name"] == "Other"  # rolled back


def test_failed_indexing_rolls_back_so_the_same_file_can_be_retried(authed: TestClient, container) -> None:
    retriever = container.retriever()
    original = retriever.ingest

    async def broken(document):
        raise RuntimeError("vector store down")

    retriever.ingest = broken
    failed = upload(authed)
    assert failed.status_code == 503 and error_code(failed) == "dependency_unavailable"
    assert authed.get("/api/documents").json()["page"]["total"] == 0
    retriever.ingest = original
    assert upload(authed).status_code == 201  # same bytes, no false "duplicate"


def test_logout_requires_csrf_header_for_cookie_sessions(client: TestClient) -> None:
    signup(client)
    del client.headers["X-ARGUS-CSRF"]
    assert client.post("/api/auth/logout").status_code == 403
    assert client.get("/api/auth/me").status_code == 200  # still signed in
    assert client.post("/api/auth/logout", headers={"X-ARGUS-CSRF": "1"}).status_code == 204


def test_pdf_files_are_viewable_inline(authed: TestClient) -> None:
    created = authed.post("/api/documents", files={"file": ("q.pdf", minimal_pdf("Revenue grew"), "application/pdf")},
                          data={"symbol": "NVDA"}).json()
    response = authed.get(f"/api/documents/{created['id']}/file")
    assert response.headers["content-type"] == "application/pdf"
    assert "content-security-policy" not in response.headers
    assert response.headers["content-disposition"].startswith("inline")


def test_saved_portfolio_without_benchmark_uses_market_default(authed: TestClient) -> None:
    indian = {"name": "India core", "rebalancing": "buy_and_hold",
              "holdings": [{"symbol": "RELIANCE.NS", "weight": 60}, {"symbol": "TCS.NS", "weight": 40}]}
    assert authed.post("/api/portfolios", json=indian).json()["benchmark"] == "^NSEI"
    us = {**indian, "name": "US core", "holdings": [{"symbol": "AAPL", "weight": 100}]}
    assert authed.post("/api/portfolios", json=us).json()["benchmark"] == "SPY"
    explicit = {**indian, "name": "India vs SPY", "benchmark": "spy"}
    assert authed.post("/api/portfolios", json=explicit).json()["benchmark"] == "SPY"
