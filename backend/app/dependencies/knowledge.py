"""Dependency wiring for persistent document retrieval."""

from functools import lru_cache

from app.core.config import settings
from app.knowledge.chunker import DocumentChunker
from app.knowledge.embeddings import ChromaDefaultEmbeddingProvider
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import ChromaVectorStore


@lru_cache
def get_knowledge_retriever() -> KnowledgeRetriever:
    """Provide a process-level persistent Chroma retrieval facade."""
    embedding_provider = ChromaDefaultEmbeddingProvider()
    vector_store = ChromaVectorStore(
        embedding_provider=embedding_provider,
        path=settings.knowledge_chroma_path,
        collection_name=settings.knowledge_collection_name,
    )
    return KnowledgeRetriever(
        vector_store,
        DocumentChunker(
            chunk_size=settings.knowledge_chunk_size,
            overlap=settings.knowledge_chunk_overlap,
        ),
    )
