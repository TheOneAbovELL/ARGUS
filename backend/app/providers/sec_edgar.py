"""SEC EDGAR client for official company filings (free, public).

SEC fair-access policy requires a descriptive ``User-Agent`` that includes
contact information and limits clients to 10 requests/second. The client is
therefore only constructed when ``ARGUS_SEC_USER_AGENT`` is configured.

SSRF safety: requests go only to fixed SEC hosts; every path component that
comes from user input or from SEC responses (CIK, accession number, document
name) is validated against a strict pattern before a URL is built.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import date

import httpx

from app.core.errors import (
    InvalidRequestError,
    NotFoundError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
SUPPORTED_FORMS = ("10-K", "10-Q", "8-K", "20-F", "40-F", "6-K")
MAX_FILING_BYTES = 20_000_000

_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(?:htm|html|txt)$")


@dataclass(frozen=True)
class Filing:
    cik: int
    company: str
    form: str
    accession: str
    filed_on: date
    report_date: date | None
    primary_document: str

    @property
    def url(self) -> str:
        return ARCHIVE_URL.format(cik=self.cik, accession=self.accession.replace("-", ""), document=self.primary_document)


class SecEdgarClient:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
        min_interval_seconds: float = 0.12,
    ) -> None:
        if "@" not in user_agent or len(user_agent) < 8:
            raise ValueError("The SEC requires a User-Agent with contact details, e.g. 'ARGUS you@example.com'.")
        self._headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self._timeout = timeout_seconds
        self._transport = transport
        self._min_interval = min_interval_seconds
        self._last_request = 0.0
        self._lock = asyncio.Lock()
        self._ciks: dict[str, tuple[int, str]] | None = None
        self._filings: dict[int, tuple[float, dict]] = {}  # cik -> (loaded_at, recent filings)
        self._ciks_loaded_at = 0.0

    async def _get(self, url: str, max_bytes: int = 5_000_000) -> httpx.Response:
        async with self._lock:  # serialize to respect the SEC request rate
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, headers=self._headers, follow_redirects=False
            ) as client, client.stream("GET", url) as response:
                # Read with a running byte cap instead of buffering an
                # arbitrarily large (possibly compressed) body first.
                chunks: list[bytes] = []
                received = 0
                if response.status_code == 200:
                    async for chunk in response.aiter_bytes():
                        received += len(chunk)
                        if received > max_bytes:
                            raise InvalidRequestError("The SEC document is too large to import.")
                        chunks.append(chunk)
                body = b"".join(chunks)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("SEC EDGAR did not respond in time.") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("SEC EDGAR could not be reached.") from exc
        if response.status_code == 404:
            raise NotFoundError("The SEC resource was not found.")
        if response.status_code in (403, 429):
            raise ProviderRateLimitedError("SEC EDGAR refused the request (rate limit or User-Agent policy).")
        if response.status_code != 200:
            # Includes 3xx: redirects are never followed, and their bodies are not filings.
            raise ProviderUnavailableError(f"SEC EDGAR returned HTTP {response.status_code}.")
        return httpx.Response(200, content=body, headers=response.headers, request=response.request)

    async def lookup(self, symbol: str) -> tuple[int, str]:
        if self._ciks is None or time.monotonic() - self._ciks_loaded_at > 24 * 3600:
            payload = (await self._get(TICKERS_URL)).json()
            self._ciks = {
                str(row["ticker"]).upper(): (int(row["cik_str"]), str(row["title"]))
                for row in payload.values()
                if isinstance(row, dict) and "ticker" in row and "cik_str" in row
            }
            self._ciks_loaded_at = time.monotonic()
        found = self._ciks.get(symbol.upper()) or self._ciks.get(symbol.upper().replace(".", "-"))
        if found is None:
            raise NotFoundError(f"'{symbol}' is not an SEC-registered ticker (EDGAR covers US filers).")
        return found

    async def filings(self, symbol: str, forms: tuple[str, ...] = SUPPORTED_FORMS, limit: int = 20) -> list[Filing]:
        cik, company = await self.lookup(symbol)
        cached = self._filings.get(cik)
        if cached and time.monotonic() - cached[0] < 3600:
            recent = cached[1]
        else:
            recent = (await self._get(SUBMISSIONS_URL.format(cik=cik))).json().get("filings", {}).get("recent", {})
            self._filings[cik] = (time.monotonic(), recent)
        columns = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
        rows = zip(*(recent.get(column, []) for column in columns))
        out: list[Filing] = []
        for form, accession, filed, report, document in rows:
            if form not in forms or not _ACCESSION.match(accession or "") or not _DOCUMENT.match(document or ""):
                continue
            out.append(
                Filing(
                    cik=cik,
                    company=company,
                    form=form,
                    accession=accession,
                    filed_on=date.fromisoformat(filed),
                    report_date=date.fromisoformat(report) if report else None,
                    primary_document=document,
                )
            )
            if len(out) >= limit:
                break
        return out

    async def find(self, symbol: str, accession: str) -> Filing:
        if not _ACCESSION.match(accession):
            raise InvalidRequestError("Accession numbers look like 0000320193-24-000123.")
        for filing in await self.filings(symbol, limit=200):
            if filing.accession == accession:
                return filing
        raise NotFoundError("That filing is not among the company's recent supported filings.")

    async def download(self, filing: Filing) -> str:
        response = await self._get(filing.url, MAX_FILING_BYTES)
        return response.text
