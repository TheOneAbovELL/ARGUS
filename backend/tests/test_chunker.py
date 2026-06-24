"""Tests for stable provenance-preserving chunks."""

from app.knowledge.chunker import DocumentChunker
from app.knowledge.document_loader import (
    DocumentPage,
    DocumentType,
    KnowledgeDocument,
)


def test_chunker_preserves_overlap_and_metadata() -> None:
    document = KnowledgeDocument(
        ticker="NVDA",
        document_type=DocumentType.TEN_K,
        title="Annual Filing",
        source="sec://nvda/10-k",
        pages=(DocumentPage(7, "one two three four five six seven"),),
    )
    chunker = DocumentChunker(chunk_size=4, overlap=2)

    chunks = chunker.chunk(document)

    assert [chunk.text for chunk in chunks] == [
        "one two three four",
        "three four five six",
        "five six seven",
    ]
    assert all(chunk.page_number == 7 for chunk in chunks)
    assert all(chunk.document_type is DocumentType.TEN_K for chunk in chunks)
    assert chunker.chunk(document)[0].id == chunks[0].id
