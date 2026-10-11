"""Retrieval: owner isolation, filters, reranking, deletion, provenance."""

import asyncio
from datetime import date

import pytest

from app.knowledge.document_loader import DocumentLoader, DocumentLoadError, DocumentType
from app.knowledge.vector_store import keyword_coverage
from tests.conftest import make_retriever

LOADER = DocumentLoader()


def doc(text: str, ticker: str, owner: str, doc_id: str, kind=DocumentType.TEN_Q):
    return LOADER.load_text(text, ticker=ticker, document_type=kind, title=f"{ticker} filing",
                            source=f"upload:{doc_id}", document_id=doc_id, owner_id=owner,
                            published_on=date(2026, 1, 15))


def test_retrieval_is_scoped_to_owner_and_ticker_with_provenance() -> None:
    retriever = make_retriever(chunk_size=12, overlap=2)
    asyncio.run(retriever.ingest(doc("Data center revenue growth accelerated and guidance was raised.", "NVDA", "u1", "d1")))
    asyncio.run(retriever.ingest(doc("Cloud revenue growth accelerated during the quarter.", "MSFT", "u1", "d2")))
    asyncio.run(retriever.ingest(doc("Data center revenue growth accelerated sharply.", "NVDA", "u2", "d3")))

    results = asyncio.run(retriever.retrieve("revenue growth guidance", "u1", "NVDA", limit=5))
    assert [r.document_id for r in results] == ["d1"]
    hit = results[0]
    assert (hit.ticker, hit.page_number, hit.document_type, hit.published_on) == ("NVDA", 1, DocumentType.TEN_Q, date(2026, 1, 15))
    assert 0 <= hit.score <= 1


def test_retrieval_requires_an_owner() -> None:
    retriever = make_retriever()
    asyncio.run(retriever.ingest(doc("text about revenue", "NVDA", "u1", "d1")))
    with pytest.raises(ValueError):
        asyncio.run(retriever.retrieve("revenue", ""))


def test_document_id_and_type_filters() -> None:
    retriever = make_retriever(chunk_size=20, overlap=2)
    asyncio.run(retriever.ingest(doc("revenue outlook improved", "NVDA", "u1", "d1")))
    asyncio.run(retriever.ingest(doc("revenue outlook improved again", "NVDA", "u1", "d2", DocumentType.EARNINGS_CALL)))
    only_d2 = asyncio.run(retriever.retrieve("revenue outlook", "u1", "NVDA", document_ids=["d2"]))
    assert {r.document_id for r in only_d2} == {"d2"}
    assert asyncio.run(retriever.retrieve("revenue outlook", "u1", "NVDA", document_ids=[])) == []
    calls = asyncio.run(retriever.retrieve("revenue outlook", "u1", document_types=(DocumentType.EARNINGS_CALL,)))
    assert {r.document_type for r in calls} == {DocumentType.EARNINGS_CALL}


def test_delete_document_removes_all_its_chunks() -> None:
    retriever = make_retriever(chunk_size=5, overlap=1)
    asyncio.run(retriever.ingest(doc("one two three four five six seven eight nine ten revenue", "NVDA", "u1", "d1")))
    assert retriever.count() > 1
    asyncio.run(retriever.delete_document("u1", "d1"))
    assert retriever.count() == 0


def test_reingestion_is_idempotent() -> None:
    retriever = make_retriever(chunk_size=5, overlap=1)
    document = doc("alpha beta gamma delta epsilon zeta eta", "NVDA", "u1", "d1")
    first = asyncio.run(retriever.ingest(document))
    asyncio.run(retriever.ingest(document))
    assert retriever.count() == first


def test_irrelevant_queries_report_insufficient_evidence() -> None:
    retriever = make_retriever()
    retriever._min_score = 0.4
    asyncio.run(retriever.ingest(doc("Semiconductor supply constraints persisted.", "NVDA", "u1", "d1")))
    assert asyncio.run(retriever.retrieve("weather forecast for tomorrow", "u1", "NVDA")) == []


def test_keyword_coverage_ignores_stopwords() -> None:
    assert keyword_coverage("what is the revenue growth", "Revenue growth was strong") == pytest.approx(1.0)
    assert keyword_coverage("the of and", "anything") == 0.0


def test_loader_rejects_binary_and_bad_pdfs() -> None:
    with pytest.raises(DocumentLoadError):
        LOADER.load_text_bytes(b"\x00\x01binary", ticker="NVDA", document_type=DocumentType.OTHER, title="t", source="s")
    with pytest.raises(DocumentLoadError):
        LOADER.load_pdf_bytes(b"%PDF-1.4 garbage", "NVDA", DocumentType.OTHER, "t", "s")
    with pytest.raises(DocumentLoadError):
        LOADER.load_pdf_bytes(b"not a pdf", "NVDA", DocumentType.OTHER, "t", "s")


def test_html_loader_strips_scripts_and_paginates() -> None:
    html = "<html><head><script>alert(1)</script></head><body><p>Item 1A. Risk Factors</p>" + "<p>word</p>" * 7000 + "</body></html>"
    document = LOADER.load_html(html, ticker="NVDA", document_type=DocumentType.TEN_K, title="10-K", source="sec")
    assert "alert" not in document.pages[0].text
    assert document.pages[0].text.startswith("Item 1A. Risk Factors")
    assert len(document.pages) == 3
