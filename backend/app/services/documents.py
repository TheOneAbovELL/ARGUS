"""Document upload, ingestion, search, and deletion for one user.

Consistency rules between the relational row (authority) and Chroma (index):

* Upload: the row is created as ``processing``; the file is stored; chunks are
  written; the row is marked ``ready``. If parsing fails the row is removed
  (422 explaining why). If storing or indexing fails, partial chunks, the file,
  and the row are all removed (503), so a retry is a plain re-upload.
* Delete: chunks are removed from Chroma first, then the row and file. If the
  index cannot be updated, the row is kept so the document stays visible and
  the delete can be retried — no orphaned, invisible chunks.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ArgusError,
    DependencyUnavailableError,
    InvalidRequestError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.db.models import Document
from app.knowledge.document_loader import DocumentLoader, DocumentLoadError, DocumentType, KnowledgeDocument
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import RetrievedChunk
from app.providers.models import normalize_symbol
from app.repositories.workspace import DocumentRepository, Page

logger = logging.getLogger("argus.documents")

_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
_HTML_SUFFIXES = {".htm", ".html"}


class DocumentUnreadableError(ArgusError):
    status_code = 422
    code = "document_unreadable"


@dataclass(frozen=True)
class UploadRequest:
    filename: str
    data: bytes
    symbol: str
    title: str | None
    document_type: DocumentType
    source_url: str | None
    published_on: date | None


def detect_kind(filename: str, data: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if data.startswith(b"%PDF-"):
        return "pdf"
    if suffix == ".pdf":
        raise UnsupportedMediaTypeError("The file has a .pdf name but is not a valid PDF.")
    if suffix in _TEXT_SUFFIXES:
        return "text"
    if suffix in _HTML_SUFFIXES:
        return "html"
    raise UnsupportedMediaTypeError("Supported formats: PDF, plain text (.txt, .md), and HTML.")


# Bound concurrent CPU-heavy parsing across all requests.
_PARSE_SLOTS = threading.BoundedSemaphore(2)

class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        owner_id: str,
        retriever: KnowledgeRetriever,
        files_dir: Path,
        max_bytes: int,
        retrieval_limit: int = 5,
    ) -> None:
        self._repo = DocumentRepository(session, owner_id)
        self._owner = owner_id
        self._retriever = retriever
        self._files_dir = files_dir / owner_id
        self._max_bytes = max_bytes
        self._limit = retrieval_limit
        self._loader = DocumentLoader()

    def file_path(self, document: Document) -> Path | None:
        matches = list(self._files_dir.glob(f"{document.id}.*")) if self._files_dir.exists() else []
        return matches[0] if matches else None

    async def upload(self, request: UploadRequest, max_bytes: int | None = None) -> Document:
        limit = max_bytes or self._max_bytes
        if not request.data:
            raise InvalidRequestError("The uploaded file is empty.")
        if len(request.data) > limit:
            raise PayloadTooLargeError(f"Files are limited to {limit // 1_000_000} MB.")
        symbol = normalize_symbol(request.symbol)
        kind = detect_kind(request.filename, request.data)
        digest = hashlib.sha256(request.data).hexdigest()
        safe_name = Path(request.filename or "document").name[:255]
        title = (request.title or Path(safe_name).stem or "Untitled document").strip()[:200]
        source = request.source_url or f"upload:{safe_name}"

        document = await self._repo.create(
            symbol=symbol,
            title=title,
            document_type=request.document_type.value,
            source=source,
            filename=safe_name,
            sha256=digest,
            size_bytes=len(request.data),
            published_on=request.published_on,
        )
        identity = {"document_id": document.id, "owner_id": self._owner, "published_on": request.published_on}
        common = {
            "ticker": symbol,
            "document_type": request.document_type,
            "title": title,
            "source": source,
            **identity,
        }
        try:
            parsed = await asyncio.to_thread(self._parse, kind, request.data, common)
        except DocumentLoadError as exc:
            await self._repo.delete(document)
            raise DocumentUnreadableError(str(exc)) from exc

        suffix = {"pdf": ".pdf", "text": ".txt", "html": ".html"}[kind]
        stored = self._files_dir / (document.id + suffix)
        try:
            await asyncio.to_thread(self._store_file, stored.name, request.data)
            chunk_count = await self._retriever.ingest(parsed)
        except Exception as exc:
            # Roll the whole upload back (chunks, file, row) so nothing is left
            # half-indexed and the same file can simply be uploaded again.
            logger.exception("document ingestion failed", extra={"document_id": document.id})
            try:
                await self._retriever.delete_document(self._owner, document.id)
            except Exception:
                logger.warning("could not remove partial chunks", extra={"document_id": document.id})
            await asyncio.to_thread(stored.unlink, missing_ok=True)
            await self._repo.delete(document)
            if isinstance(exc, ArgusError):  # e.g. embedding model not downloaded yet
                raise
            raise DependencyUnavailableError(
                "The document could not be indexed right now. Nothing was saved; please upload it again."
            ) from exc
        return await self._repo.mark(document, "ready", len(parsed.pages), chunk_count)

    def _parse(self, kind: str, data: bytes, common: dict) -> KnowledgeDocument:
        with _PARSE_SLOTS:
            return self._parse_unbounded(kind, data, common)

    def _parse_unbounded(self, kind: str, data: bytes, common: dict) -> KnowledgeDocument:
        if kind == "pdf":
            return self._loader.load_pdf_bytes(data, **common)
        if kind == "html":
            return self._loader.load_html(data.decode("utf-8", errors="replace"), **common)
        return self._loader.load_text_bytes(data, **common)

    def _store_file(self, name: str, data: bytes) -> None:
        self._files_dir.mkdir(parents=True, exist_ok=True)
        (self._files_dir / name).write_bytes(data)

    async def list(self, limit: int, offset: int, symbol: str | None = None) -> Page:
        return await self._repo.list(limit, offset, normalize_symbol(symbol) if symbol else None)

    async def get(self, document_id: str) -> Document:
        return await self._repo.get(document_id)

    async def delete(self, document_id: str) -> None:
        document = await self._repo.get(document_id)
        try:
            await self._retriever.delete_document(self._owner, document.id)
        except Exception as exc:
            raise DependencyUnavailableError(
                "The document index is unavailable; the document was not deleted. Please retry."
            ) from exc
        path = self.file_path(document)
        await self._repo.delete(document)
        if path is not None:
            await asyncio.to_thread(path.unlink, missing_ok=True)

    async def search(
        self, query: str, symbol: str | None = None, limit: int | None = None
    ) -> list[RetrievedChunk]:
        cleaned = query.strip()
        if not 2 <= len(cleaned) <= 500:
            raise InvalidRequestError("Search queries must be 2-500 characters.")
        symbol = normalize_symbol(symbol) if symbol else None
        ready = await self._repo.ready_ids(symbol)
        return await self._retriever.retrieve(
            cleaned, self._owner, symbol, min(limit or self._limit, 20), document_ids=ready
        )
