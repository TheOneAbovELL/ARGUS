"""Chroma-backed storage for embedded document chunks."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from app.knowledge.chunker import DocumentChunk
from app.knowledge.document_loader import DocumentType
from app.knowledge.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    text: str
    score: float
    ticker: str
    document_type: DocumentType
    title: str
    source: str
    page_number: int
    chunk_index: int


class ChromaVectorStore:
    """Persist and query ARGUS knowledge chunks through Chroma."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        path: str | Path = ".argus/chroma",
        collection_name: str = "argus_knowledge",
        client: Any | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._client = client or chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[DocumentChunk]) -> int:
        """Embed and idempotently store chunks using stable IDs."""
        if not chunks:
            return 0
        self._collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=self._embedding_provider.embed_documents(
                [chunk.text for chunk in chunks]
            ),
            metadatas=[
                {
                    "ticker": chunk.ticker,
                    "document_type": chunk.document_type.value,
                    "title": chunk.title,
                    "source": chunk.source,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
        )
        return len(chunks)

    def query(
        self,
        query: str,
        ticker: str,
        limit: int = 5,
        document_types: tuple[DocumentType, ...] | None = None,
    ) -> list[RetrievedChunk]:
        """Return nearest ticker-scoped chunks with provenance."""
        if limit < 1:
            raise ValueError("limit must be positive.")
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[self._embedding_provider.embed_query(query)],
            n_results=min(max(limit * 4, limit), self._collection.count()),
            where={"ticker": ticker.strip().upper()},
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []
        allowed = set(document_types or ())
        retrieved: list[RetrievedChunk] = []
        for chunk_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            document_type = DocumentType(metadata["document_type"])
            if allowed and document_type not in allowed:
                continue
            retrieved.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=text,
                    score=1.0 - float(distance),
                    ticker=metadata["ticker"],
                    document_type=document_type,
                    title=metadata["title"],
                    source=metadata["source"],
                    page_number=int(metadata["page_number"]),
                    chunk_index=int(metadata["chunk_index"]),
                )
            )
            if len(retrieved) == limit:
                break
        return retrieved
