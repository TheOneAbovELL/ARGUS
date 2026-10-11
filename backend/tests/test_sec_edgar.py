"""SEC EDGAR client and filing import — offline via a mock HTTP transport."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.errors import InvalidRequestError, NotFoundError, ProviderRateLimitedError
from app.providers.sec_edgar import SecEdgarClient

TICKERS = {"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"}}
SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["4", "10-Q", "10-K", "8-K"],
            "accessionNumber": ["0001045810-26-000001", "0001045810-26-000050", "0001045810-26-000020", "bad-accession"],
            "filingDate": ["2026-05-01", "2026-05-28", "2026-02-25", "2026-01-10"],
            "reportDate": ["", "2026-04-26", "2026-01-25", ""],
            "primaryDocument": ["x.xml", "nvda-20260426.htm", "nvda-20260125.htm", "evil/../x.htm"],
        }
    }
}
FILING_HTML = (
    "<html><body><script>steal()</script><p>Item 1A. Risk Factors</p>"
    "<p>We rely on third-party foundries in Taiwan; export controls may limit data center sales.</p></body></html>"
)


def transport(requests: list[str], status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        assert request.headers["user-agent"] == "ARGUS tests ops@example.com"
        if status != 200:
            return httpx.Response(status)
        if request.url.path == "/files/company_tickers.json":
            return httpx.Response(200, json=TICKERS)
        if request.url.host == "data.sec.gov":
            return httpx.Response(200, json=SUBMISSIONS)
        if request.url.path.endswith("nvda-20260125.htm"):
            return httpx.Response(200, text=FILING_HTML)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def sec_client(requests: list[str], status: int = 200) -> SecEdgarClient:
    return SecEdgarClient("ARGUS tests ops@example.com", transport=transport(requests, status), min_interval_seconds=0)


def test_user_agent_with_contact_is_required() -> None:
    with pytest.raises(ValueError):
        SecEdgarClient("ARGUS")


def test_filings_are_filtered_and_validated() -> None:
    requests: list[str] = []
    filings = asyncio.run(sec_client(requests).filings("nvda"))
    assert [(f.form, f.accession) for f in filings] == [("10-Q", "0001045810-26-000050"), ("10-K", "0001045810-26-000020")]
    assert filings[1].url == "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000020/nvda-20260125.htm"
    assert all(url.startswith(("https://www.sec.gov/", "https://data.sec.gov/")) for url in requests)


def test_unknown_ticker_and_bad_accession() -> None:
    sec = sec_client([])
    with pytest.raises(NotFoundError):
        asyncio.run(sec.filings("ZZZZ"))
    with pytest.raises(InvalidRequestError):
        asyncio.run(sec.find("NVDA", "../../etc/passwd"))
    with pytest.raises(NotFoundError):
        asyncio.run(sec.find("NVDA", "0001045810-99-999999"))


def test_sec_refusals_map_to_typed_errors() -> None:
    with pytest.raises(ProviderRateLimitedError):
        asyncio.run(sec_client([], status=403).filings("NVDA"))


def test_filings_api_requires_configuration(client: TestClient) -> None:
    response = client.get("/api/filings/NVDA")
    assert response.status_code == 503 and "ARGUS_SEC_USER_AGENT" in response.json()["error"]["message"]


def test_import_sec_filing_indexes_it_as_a_document(authed: TestClient, container) -> None:
    container.sec = sec_client([])
    listing = authed.get("/api/filings/NVDA").json()
    assert listing[1]["form"] == "10-K"
    imported = authed.post("/api/documents/import-sec", json={"symbol": "NVDA", "accession": "0001045810-26-000020"})
    assert imported.status_code == 201, imported.text
    document = imported.json()
    assert document["document_type"] == "10-K" and document["published_on"] == "2026-02-25"
    assert document["source"].startswith("https://www.sec.gov/Archives/")
    search = authed.post("/api/documents/search", json={"query": "foundries Taiwan export controls", "symbol": "NVDA"}).json()
    assert search["passages"] and "steal" not in search["passages"][0]["text"]
