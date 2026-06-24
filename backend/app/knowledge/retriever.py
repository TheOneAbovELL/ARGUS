"""Async ingestion and retrieval facade for research agents."""

import asyncio

from app.knowledge.chunker import DocumentChunker
from app.knowledge.document_loader import DocumentType, KnowledgeDocument
from app.knowledge.vector_store import ChromaVectorStore, RetrievedChunk


class KnowledgeRetriever:
    """Coordinate chunking, storage, and ticker-scoped semantic retrieval."""

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        chunker: DocumentChunker | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._chunker = chunker or DocumentChunker()

    async def ingest(self, document: KnowledgeDocument) -> int:
        """Chunk, embed, and persist a normalized document."""
        chunks = self._chunker.chunk(document)
        return await asyncio.to_thread(self._vector_store.upsert, chunks)

    async def retrieve(
        self,
        query: str,
        ticker: str,
        limit: int = 5,
        document_types: tuple[DocumentType, ...] | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant evidence without blocking the event loop."""
        return await asyncio.to_thread(
            self._vector_store.query,
            query,
            ticker,
            limit,
            document_types,
        )
