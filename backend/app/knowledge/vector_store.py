"""Chroma-backed storage and hybrid retrieval for embedded document chunks.

Every chunk is stored with ``owner_id`` and ``document_id`` metadata and every
query filters on ``owner_id`` inside Chroma, so one user's documents can never
be retrieved for another user.

Retrieval is "dense first, lexical rerank": Chroma returns the nearest
``limit * 5`` candidates by cosine similarity; candidates are then rescored as
``0.75 * dense + 0.25 * keyword_coverage``, near-duplicates are removed, at
most ``max_per_document`` chunks are kept per document (source diversity), and
results below ``min_score`` are discarded so weak matches are reported as
insufficient evidence instead of being passed off as support.
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import chromadb

from app.knowledge.chunker import DocumentChunk
from app.knowledge.document_loader import DocumentType
from app.knowledge.embeddings import EmbeddingProvider

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was "
    "were will with what how why which who when does do did about into over than their our we".split()
)
DENSE_WEIGHT = 0.75


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
    document_id: str = ""
    published_on: date | None = None
    dense_score: float = 0.0
    lexical_score: float = 0.0


def query_terms(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


def keyword_coverage(query: str, text: str) -> float:
    terms = query_terms(query)
    if not terms:
        return 0.0
    tokens = set(_TOKEN.findall(text.lower()))
    return len(terms & tokens) / len(terms)


class ChromaVectorStore:
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

    def count(self) -> int:
        return self._collection.count()

    def upsert(self, chunks: list[DocumentChunk], batch_size: int = 128) -> int:
        """Embed and idempotently store chunks using stable IDs."""
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            self._collection.upsert(
                ids=[chunk.id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                embeddings=self._embedding_provider.embed_documents([c.text for c in batch]),
                metadatas=[_metadata(chunk) for chunk in batch],
            )
        return len(chunks)

    def delete_document(self, owner_id: str, document_id: str) -> None:
        self._collection.delete(
            where={"$and": [{"owner_id": owner_id}, {"document_id": document_id}]}
        )

    def query(
        self,
        query: str,
        owner_id: str,
        ticker: str | None = None,
        limit: int = 5,
        document_types: tuple[DocumentType, ...] | None = None,
        document_ids: Sequence[str] | None = None,
        min_score: float = 0.0,
        max_per_document: int = 2,
    ) -> list[RetrievedChunk]:
        """Return the best owner-scoped chunks with provenance."""
        if limit < 1:
            raise ValueError("limit must be positive.")
        if not owner_id:
            raise ValueError("owner_id is required for retrieval.")
        total = self._collection.count()
        if total == 0:
            return []
        conditions: list[dict[str, Any]] = [{"owner_id": owner_id}]
        if ticker:
            conditions.append({"ticker": ticker.strip().upper()})
        if document_types:
            conditions.append({"document_type": {"$in": [t.value for t in document_types]}})
        if document_ids is not None:
            if not document_ids:
                return []
            conditions.append({"document_id": {"$in": list(document_ids)}})
        where = conditions[0] if len(conditions) == 1 else {"$and": conditions}
        result = self._collection.query(
            query_embeddings=[self._embedding_provider.embed_query(query)],
            n_results=min(limit * 5, total),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0] or []
        metadatas = (result.get("metadatas") or [[]])[0] or []
        distances = (result.get("distances") or [[]])[0] or []

        candidates: list[RetrievedChunk] = []
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            dense = max(0.0, 1.0 - float(distance))
            lexical = keyword_coverage(query, text)
            published = metadata.get("published_on") or None
            candidates.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=text,
                    score=DENSE_WEIGHT * dense + (1 - DENSE_WEIGHT) * lexical,
                    ticker=metadata["ticker"],
                    document_type=DocumentType(metadata["document_type"]),
                    title=metadata["title"],
                    source=metadata["source"],
                    page_number=int(metadata["page_number"]),
                    chunk_index=int(metadata["chunk_index"]),
                    document_id=metadata.get("document_id", ""),
                    published_on=date.fromisoformat(published) if published else None,
                    dense_score=dense,
                    lexical_score=lexical,
                )
            )
        candidates.sort(key=lambda c: c.score, reverse=True)

        selected: list[RetrievedChunk] = []
        seen_text: set[str] = set()
        per_document: dict[str, int] = {}
        for candidate in candidates:
            if candidate.score < min_score:
                continue
            fingerprint = hashlib.sha1(" ".join(candidate.text.lower().split()).encode()).hexdigest()
            if fingerprint in seen_text:
                continue
            key = candidate.document_id or candidate.source
            if per_document.get(key, 0) >= max_per_document:
                continue
            seen_text.add(fingerprint)
            per_document[key] = per_document.get(key, 0) + 1
            selected.append(candidate)
            if len(selected) == limit:
                break
        return selected


def _metadata(chunk: DocumentChunk) -> dict[str, Any]:
    return {
        "owner_id": chunk.owner_id,
        "document_id": chunk.document_id,
        "ticker": chunk.ticker,
        "document_type": chunk.document_type.value,
        "title": chunk.title,
        "source": chunk.source,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "published_on": chunk.published_on.isoformat() if chunk.published_on else "",
    }
