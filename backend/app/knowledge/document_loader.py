"""Load company documents while preserving source and page provenance."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pypdf import PdfReader


class DocumentType(StrEnum):
    TEN_K = "10-K"
    TEN_Q = "10-Q"
    ANNUAL_REPORT = "annual_report"
    EARNINGS_CALL = "earnings_call"
    INVESTOR_PRESENTATION = "investor_presentation"


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


class DocumentLoadError(ValueError):
    """Raised when a source cannot produce usable text."""


class DocumentLoader:
    """Load PDFs and text transcripts into one normalized document model."""

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
        try:
            reader = PdfReader(file_path)
            extracted_pages = []
            for index, page in enumerate(reader.pages):
                text = self._normalize(page.extract_text() or "")
                if text:
                    extracted_pages.append(DocumentPage(index + 1, text))
            pages = tuple(extracted_pages)
        except Exception as exc:
            raise DocumentLoadError(f"Unable to read PDF: {file_path.name}") from exc
        if not pages:
            raise DocumentLoadError(
                "The PDF contains no extractable text; scanned PDFs require OCR."
            )
        return KnowledgeDocument(
            ticker=self._normalize_ticker(ticker),
            document_type=document_type,
            title=title or file_path.stem,
            source=source or str(file_path.resolve()),
            pages=pages,
        )

    def load_text(
        self,
        text: str,
        ticker: str,
        document_type: DocumentType,
        title: str,
        source: str,
    ) -> KnowledgeDocument:
        normalized = self._normalize(text)
        if not normalized:
            raise DocumentLoadError("Document text must not be empty.")
        return KnowledgeDocument(
            ticker=self._normalize_ticker(ticker),
            document_type=document_type,
            title=title,
            source=source,
            pages=(DocumentPage(1, normalized),),
        )

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        normalized = ticker.strip().upper()
        if not normalized or not normalized.isalnum():
            raise DocumentLoadError("Ticker must contain only letters and numbers.")
        return normalized
