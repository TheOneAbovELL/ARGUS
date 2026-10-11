"""Load company documents while preserving source and page provenance.

All inputs are treated as untrusted: file type is verified by content (magic
bytes), size and page counts are bounded, encrypted PDFs are rejected, and
extracted text is only ever stored and quoted — never executed or followed.
"""

import io
import re
import time
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

MAX_PDF_PAGES = 600
MAX_TEXT_CHARS = 3_000_000
# Text extraction cost grows with a page's (decompressed) content stream, which
# a tiny crafted PDF can make enormous. Bound both bytes and wall-clock time.
MAX_PAGE_CONTENT_BYTES = 2_000_000
MAX_PDF_CONTENT_BYTES = 50_000_000
MAX_PDF_PARSE_SECONDS = 120.0


class DocumentType(StrEnum):
    TEN_K = "10-K"
    TEN_Q = "10-Q"
    EIGHT_K = "8-K"
    TWENTY_F = "20-F"
    ANNUAL_REPORT = "annual_report"
    EARNINGS_CALL = "earnings_call"
    INVESTOR_PRESENTATION = "investor_presentation"
    RESEARCH_NOTE = "research_note"
    OTHER = "other"


@dataclass(frozen=True)
class DocumentPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class KnowledgeDocument:
    ticker: str
    document_type: DocumentType
    title: str
    source: str
    pages: tuple[DocumentPage, ...]
    document_id: str = ""
    owner_id: str = ""
    published_on: date | None = None


class DocumentLoadError(ValueError):
    """Raised when a source cannot produce usable text."""


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "head", "title", "noscript"}
    _BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


class DocumentLoader:
    """Load PDFs, plain text, and HTML into one normalized document model."""

    def load_pdf(
        self,
        path: str | Path,
        ticker: str,
        document_type: DocumentType,
        title: str | None = None,
        source: str | None = None,
    ) -> KnowledgeDocument:
        file_path = Path(path)
        if file_path.suffix.lower() != ".pdf" or not file_path.is_file():
            raise DocumentLoadError("A readable PDF file is required.")
        return self.load_pdf_bytes(
            file_path.read_bytes(),
            ticker,
            document_type,
            title or file_path.stem,
            source or str(file_path.resolve()),
        )

    def load_pdf_bytes(
        self,
        data: bytes,
        ticker: str,
        document_type: DocumentType,
        title: str,
        source: str,
        **identity,
    ) -> KnowledgeDocument:
        if not data.startswith(b"%PDF-"):
            raise DocumentLoadError("The file is not a valid PDF.")
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise DocumentLoadError("Encrypted PDFs are not supported.")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise DocumentLoadError(f"PDFs are limited to {MAX_PDF_PAGES} pages.")
            pages: list[DocumentPage] = []
            total = 0
            content_bytes = 0
            started = time.monotonic()
            for index, page in enumerate(reader.pages):
                contents = page.get_contents()
                size = len(contents.get_data()) if contents is not None else 0
                content_bytes += size
                if size > MAX_PAGE_CONTENT_BYTES or content_bytes > MAX_PDF_CONTENT_BYTES:
                    raise DocumentLoadError("The PDF's page content is too large or complex to index.")
                if time.monotonic() - started > MAX_PDF_PARSE_SECONDS:
                    raise DocumentLoadError("The PDF took too long to parse; it may be malformed or unusually complex.")
                text = self._normalize(page.extract_text() or "")
                total += len(text)
                if total > MAX_TEXT_CHARS:
                    raise DocumentLoadError("The document contains too much text to index.")
                if text:
                    pages.append(DocumentPage(index + 1, text))
        except DocumentLoadError:
            raise
        except Exception as exc:
            raise DocumentLoadError("Unable to read the PDF; it may be corrupted.") from exc
        if not pages:
            raise DocumentLoadError(
                "The PDF contains no extractable text. Scanned PDFs need OCR, which ARGUS does not perform."
            )
        return self._build(ticker, document_type, title, source, tuple(pages), **identity)

    def load_text(
        self,
        text: str,
        ticker: str,
        document_type: DocumentType,
        title: str,
        source: str,
        **identity,
    ) -> KnowledgeDocument:
        if len(text) > MAX_TEXT_CHARS:
            raise DocumentLoadError("The document contains too much text to index.")
        normalized = self._normalize(text)
        if not normalized:
            raise DocumentLoadError("Document text must not be empty.")
        return self._build(
            ticker, document_type, title, source, (DocumentPage(1, normalized),), **identity
        )

    def load_text_bytes(self, data: bytes, **kwargs) -> KnowledgeDocument:
        if b"\x00" in data[:4096]:
            raise DocumentLoadError("The file appears to be binary, not text.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentLoadError("Text files must be UTF-8 encoded.") from exc
        return self.load_text(text, **kwargs)

    def load_html(self, html: str, **kwargs) -> KnowledgeDocument:
        """Extract visible text from HTML (e.g. SEC EDGAR filings), splitting
        it into pseudo-pages of ~3,000 words so citations stay locatable."""
        parser = _TextExtractor()
        try:
            parser.feed(html)
        except Exception as exc:
            raise DocumentLoadError("Unable to parse the HTML document.") from exc
        extracted = self._normalize("".join(parser.parts))
        if len(extracted) > MAX_TEXT_CHARS:
            raise DocumentLoadError("The document contains too much text to index.")
        words = extracted.split(" ")
        if not words or words == [""]:
            raise DocumentLoadError("The HTML document contains no text.")
        size = 3_000
        pages = tuple(
            DocumentPage(index // size + 1, " ".join(words[index : index + size]))
            for index in range(0, len(words), size)
        )
        return self._build(pages=pages, **kwargs)

    def _build(
        self,
        ticker: str,
        document_type: DocumentType,
        title: str,
        source: str,
        pages: tuple[DocumentPage, ...],
        document_id: str = "",
        owner_id: str = "",
        published_on: date | None = None,
    ) -> KnowledgeDocument:
        return KnowledgeDocument(
            ticker=self._normalize_ticker(ticker),
            document_type=document_type,
            title=title,
            source=source,
            pages=pages,
            document_id=document_id,
            owner_id=owner_id,
            published_on=published_on,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        normalized = ticker.strip().upper()
        if not normalized or not re.fullmatch(r"[A-Z0-9^][A-Z0-9.\-=^]{0,14}", normalized):
            raise DocumentLoadError("Ticker must be a valid symbol.")
        return normalized
