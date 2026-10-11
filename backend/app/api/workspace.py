"""Watchlist and document routes (signed-in users only)."""

import asyncio
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import ContainerDep, CurrentUser, DbDep, provider_rate_limit
from app.core.errors import ConflictError, DependencyUnavailableError, NotFoundError, PayloadTooLargeError
from app.knowledge.document_loader import DocumentType
from app.providers.models import normalize_symbol
from app.repositories.workspace import DocumentRepository, WatchlistRepository
from app.schemas.common import PageMeta
from app.schemas.workspace import (
    DocumentList,
    DocumentOut,
    DocumentSearchIn,
    DocumentSearchOut,
    FilingOut,
    PassageOut,
    SecImportIn,
    WatchlistIn,
    WatchlistItemOut,
)
from app.services.documents import DocumentService, UploadRequest

router = APIRouter(prefix="/api", tags=["workspace"])

_MEDIA_TYPES = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8", ".html": "text/plain; charset=utf-8"}


# ── watchlist ─────────────────────────────────────────────────────────


@router.get("/watchlist", response_model=list[WatchlistItemOut])
async def get_watchlist(user: CurrentUser, db: DbDep):
    return [WatchlistItemOut.of(i) for i in await WatchlistRepository(db, user.id).list()]


@router.post("/watchlist", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(body: WatchlistIn, user: CurrentUser, db: DbDep):
    item = await WatchlistRepository(db, user.id).add(normalize_symbol(body.symbol))
    return WatchlistItemOut.of(item)


@router.delete("/watchlist/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(symbol: str, user: CurrentUser, db: DbDep) -> Response:
    await WatchlistRepository(db, user.id).remove(normalize_symbol(symbol))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── documents ─────────────────────────────────────────────────────────


def _documents(container, db, user) -> DocumentService:
    return DocumentService(
        db,
        user.id,
        container.retriever(),
        container.files_dir,
        container.settings.max_upload_bytes,
        container.settings.knowledge_retrieval_limit,
    )


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    """Read at most ``limit`` bytes; never trust the declared size."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise PayloadTooLargeError(f"Files are limited to {limit // 1_000_000} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    user: CurrentUser,
    db: DbDep,
    container: ContainerDep,
    file: UploadFile = File(...),
    symbol: str = Form(..., max_length=16),
    document_type: DocumentType = Form(DocumentType.OTHER),
    title: str | None = Form(None, max_length=200),
    source_url: str | None = Form(None, max_length=500),
    published_on: date | None = Form(None),
):
    container.upload_limiter.check(f"user:{user.id}", "Too many document uploads; please wait a minute.")
    if source_url and not source_url.startswith(("http://", "https://")):
        source_url = None  # stored as provenance text only; never fetched
    data = await _read_limited(file, container.settings.max_upload_bytes)
    service = await asyncio.to_thread(_documents, container, db, user)
    document = await service.upload(
        UploadRequest(
            filename=file.filename or "document",
            data=data,
            symbol=symbol,
            title=title,
            document_type=document_type,
            source_url=source_url,
            published_on=published_on,
        )
    )
    return DocumentOut.of(document)


@router.get("/documents", response_model=DocumentList)
async def list_documents(
    user: CurrentUser,
    db: DbDep,
    container: ContainerDep,
    symbol: str | None = Query(None, max_length=16),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    service = await asyncio.to_thread(_documents, container, db, user)
    page = await service.list(limit, offset, symbol)
    return DocumentList(
        items=[DocumentOut.of(d) for d in page.items],
        page=PageMeta(total=page.total, limit=limit, offset=offset),
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, user: CurrentUser, db: DbDep, container: ContainerDep):
    service = await asyncio.to_thread(_documents, container, db, user)
    return DocumentOut.of(await service.get(document_id))


@router.get("/documents/{document_id}/file")
async def download_document(document_id: str, user: CurrentUser, db: DbDep, container: ContainerDep):
    """Serve the original upload so citations can be opened at their page
    (``#page=N`` for PDFs). HTML is served as plain text so it never renders
    or runs scripts in the ARGUS origin."""
    service = await asyncio.to_thread(_documents, container, db, user)
    document = await service.get(document_id)
    path = service.file_path(document)
    if path is None:
        raise NotFoundError("The original file is not available.")
    headers = {"Cache-Control": "private, no-store"}
    if path.suffix != ".pdf":
        # Text/HTML is served as text/plain and additionally sandboxed. PDFs are
        # not: Chromium's built-in viewer will not render a sandboxed PDF, which
        # would break #page=N citation links (the viewer isolates PDF content).
        headers["Content-Security-Policy"] = "sandbox"
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
        filename=document.filename or path.name,
        content_disposition_type="inline",
        headers=headers,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, user: CurrentUser, db: DbDep, container: ContainerDep) -> Response:
    service = await asyncio.to_thread(_documents, container, db, user)
    await service.delete(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/search", response_model=DocumentSearchOut)
async def search_documents(body: DocumentSearchIn, user: CurrentUser, db: DbDep, container: ContainerDep):
    service = await asyncio.to_thread(_documents, container, db, user)
    passages = await service.search(body.query, body.symbol, body.limit)
    return DocumentSearchOut(
        query=body.query,
        passages=[PassageOut.of(p) for p in passages],
        insufficient_evidence=not passages,
    )


# ── SEC EDGAR filings (free, official) ────────────────────────────────

_FORM_TYPES = {"10-K": DocumentType.TEN_K, "10-Q": DocumentType.TEN_Q, "8-K": DocumentType.EIGHT_K,
               "20-F": DocumentType.TWENTY_F}


def _require_sec(container):
    if container.sec is None:
        raise DependencyUnavailableError(
            "SEC EDGAR is not configured. Set ARGUS_SEC_USER_AGENT to a name and contact email "
            "(SEC fair-access policy) to enable filings."
        )
    return container.sec


@router.get("/filings/{symbol}", response_model=list[FilingOut], tags=["filings"],
            dependencies=[Depends(provider_rate_limit)])
async def list_filings(symbol: str, container: ContainerDep, limit: int = Query(20, ge=1, le=50)):
    sec = _require_sec(container)
    filings = await sec.filings(normalize_symbol(symbol), limit=limit)
    return [
        FilingOut(form=f.form, accession=f.accession, filed_on=f.filed_on, report_date=f.report_date,
                  company=f.company, url=f.url)
        for f in filings
    ]


@router.post("/documents/import-sec", response_model=DocumentOut, status_code=status.HTTP_201_CREATED,
             tags=["filings"])
async def import_sec_filing(body: SecImportIn, user: CurrentUser, db: DbDep, container: ContainerDep):
    """Download a filing's primary document from EDGAR and index it like an
    upload. Large 10-Ks can take tens of seconds to embed on CPU."""
    sec = _require_sec(container)
    container.upload_limiter.check(f"user:{user.id}", "Too many document uploads; please wait a minute.")
    symbol = normalize_symbol(body.symbol)
    filing = await sec.find(symbol, body.accession)
    # Check before downloading so repeated imports don't spend the SEC budget.
    if await DocumentRepository(db, user.id).find_by_source(filing.url) is not None:
        raise ConflictError("You have already imported this filing.")
    html = await sec.download(filing)
    service = await asyncio.to_thread(_documents, container, db, user)
    document = await service.upload(
        UploadRequest(
            filename=f"{filing.accession}.html",
            data=html.encode("utf-8"),
            symbol=symbol,
            title=f"{filing.company} {filing.form} (filed {filing.filed_on.isoformat()})",
            document_type=_FORM_TYPES.get(filing.form, DocumentType.OTHER),
            source_url=filing.url,
            published_on=filing.filed_on,
        ),
        max_bytes=20_000_000,
    )
    return DocumentOut.of(document)
