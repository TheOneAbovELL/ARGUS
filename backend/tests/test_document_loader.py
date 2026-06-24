"""Tests for normalized document ingestion."""

import pytest

from app.knowledge.document_loader import (
    DocumentLoadError,
    DocumentLoader,
    DocumentType,
)


def test_text_loader_supports_earnings_call_transcripts() -> None:
    document = DocumentLoader().load_text(
        "Revenue grew strongly.\n Management raised guidance.",
        ticker=" nvda ",
        document_type=DocumentType.EARNINGS_CALL,
        title="Q1 Earnings Call",
        source="https://example.com/transcript",
    )

    assert document.ticker == "NVDA"
    assert document.document_type is DocumentType.EARNINGS_CALL
    assert document.pages[0].text == "Revenue grew strongly. Management raised guidance."


def test_pdf_loader_rejects_non_pdf_sources(tmp_path) -> None:
    path = tmp_path / "filing.txt"
    path.write_text("not a PDF", encoding="utf-8")
    with pytest.raises(DocumentLoadError):
        DocumentLoader().load_pdf(path, "NVDA", DocumentType.TEN_K)
