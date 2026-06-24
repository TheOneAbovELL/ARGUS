"""Integration tests for Chroma-backed knowledge retrieval."""

import asyncio

import chromadb

from app.knowledge.chunker import DocumentChunker
from app.knowledge.document_loader import DocumentLoader, DocumentType
from app.knowledge.embeddings import HashEmbeddingProvider
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import ChromaVectorStore


def make_retriever() -> KnowledgeRetriever:
    store = ChromaVectorStore(
        embedding_provider=HashEmbeddingProvider(64),
        collection_name="argus_test_knowledge",
        client=chromadb.EphemeralClient(),
    )
    return KnowledgeRetriever(store, DocumentChunker(chunk_size=12, overlap=2))


def test_retriever_returns_ticker_scoped_chunks_with_provenance() -> None:
    retriever = make_retriever()
    loader = DocumentLoader()
    nvda = loader.load_text(
        "Data center revenue growth accelerated and management raised guidance.",
        "NVDA",
        DocumentType.TEN_Q,
        "NVIDIA Q1 10-Q",
        "sec://nvda/q1",
    )
    msft = loader.load_text(
        "Cloud revenue increased during the quarter.",
        "MSFT",
        DocumentType.TEN_Q,
        "Microsoft Q1 10-Q",
        "sec://msft/q1",
    )

    assert asyncio.run(retriever.ingest(nvda)) == 1
    asyncio.run(retriever.ingest(msft))
    results = asyncio.run(
        retriever.retrieve("revenue growth guidance", "NVDA", limit=3)
    )

    assert len(results) == 1
    assert results[0].ticker == "NVDA"
    assert results[0].document_type is DocumentType.TEN_Q
    assert results[0].source == "sec://nvda/q1"
    assert results[0].page_number == 1
