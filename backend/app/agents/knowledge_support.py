"""Shared conversion of retrieved evidence into agent-safe context."""

from app.agents.models import DocumentCitation
from app.knowledge.vector_store import RetrievedChunk


def insights_from(chunks: list[RetrievedChunk]) -> tuple[str, ...]:
    """Return concise extractive evidence without inventing a summary."""
    return tuple(chunk.text[:500] for chunk in chunks)


def citations_from(chunks: list[RetrievedChunk]) -> tuple[DocumentCitation, ...]:
    return tuple(
        DocumentCitation(
            title=chunk.title,
            document_type=chunk.document_type.value,
            source=chunk.source,
            page_number=chunk.page_number,
            chunk_id=chunk.id,
            score=chunk.score,
        )
        for chunk in chunks
    )
