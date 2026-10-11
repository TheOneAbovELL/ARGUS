"""Shared fixtures: an isolated, fully offline ARGUS instance per test.

Every test app uses deterministic fixture market data pinned to a fixed date,
a temporary SQLite database migrated with Alembic, an in-memory Chroma client
with hash embeddings, and no language model — so the suite needs no network,
no paid API, and no credentials.
"""

import itertools
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import chromadb
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import Container
from app.knowledge.chunker import DocumentChunker
from app.knowledge.embeddings import HashEmbeddingProvider
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import ChromaVectorStore
from app.main import create_app
from app.providers.cache import CachingMarketDataProvider
from app.providers.fixture import FixtureMarketDataProvider

FIXED_TODAY = date(2026, 6, 30)
_collections = itertools.count()


def make_retriever(chunk_size: int = 60, overlap: int = 10) -> KnowledgeRetriever:
    store = ChromaVectorStore(
        embedding_provider=HashEmbeddingProvider(256),
        collection_name=f"argus_test_{next(_collections)}",
        client=chromadb.EphemeralClient(),
    )
    return KnowledgeRetriever(store, DocumentChunker(chunk_size, overlap), min_score=0.05)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        market_data_provider="fixture",
        data_dir=tmp_path,
        embedding_provider="hash",
        llm_provider="none",
        auth_rate_limit_per_minute=50,
        research_rate_limit_per_minute=50,
        _env_file=None,
    )


@pytest.fixture
def container(settings: Settings) -> Container:
    provider = CachingMarketDataProvider(
        FixtureMarketDataProvider(today=FIXED_TODAY), today=lambda: FIXED_TODAY
    )
    built = Container(settings, provider=provider, retriever_factory=make_retriever, use_configured_llm=False)
    built.market._today = lambda: FIXED_TODAY  # windows resolve against the fixture's date
    return built


@pytest.fixture
def client(settings: Settings, container: Container) -> Iterator[TestClient]:
    app = create_app(settings, container)
    with TestClient(app) as test_client:
        yield test_client


def signup(client: TestClient, email: str = "analyst@example.com", password: str = "correct horse battery") -> dict:
    response = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    client.headers["X-ARGUS-CSRF"] = "1"
    return response.json()


@pytest.fixture
def authed(client: TestClient) -> TestClient:
    signup(client)
    return client
