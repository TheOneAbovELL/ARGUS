"""Async ingestion and retrieval facade (keeps blocking work off the event loop)."""

import asyncio
from collections.abc import Sequence

from app.knowledge.chunker import DocumentChunker
from app.knowledge.document_loader import DocumentType, KnowledgeDocument
from app.knowledge.vector_store import ChromaVectorStore, RetrievedChunk


class KnowledgeRetriever:
    def __init__(
        self,
        vector_store: ChromaVectorStore,
        chunker: DocumentChunker | None = None,
        min_score: float = 0.0,
    ) -> None:
        self._vector_store = vector_store
        self._chunker = chunker or DocumentChunker()
        self._min_score = min_score

    async def ingest(self, document: KnowledgeDocument) -> int:
        """Chunk, embed, and persist a normalized document."""
        if not document.owner_id:
            raise ValueError("Documents must have an owner before ingestion.")
        chunks = self._chunker.chunk(document)
        return await asyncio.to_thread(self._vector_store.upsert, chunks)

    def count(self) -> int:
        return self._vector_store.count()

    async def delete_document(self, owner_id: str, document_id: str) -> None:
        await asyncio.to_thread(self._vector_store.delete_document, owner_id, document_id)

    async def retrieve(
        self,
        query: str,
        owner_id: str,
        ticker: str | None = None,
        limit: int = 5,
        document_types: tuple[DocumentType, ...] | None = None,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        return await asyncio.to_thread(
            self._vector_store.query,
            query,
            owner_id,
            ticker,
            limit,
            document_types,
            document_ids,
            self._min_score,
        )
