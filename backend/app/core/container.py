"""Application composition root.

All long-lived collaborators are built once here (at startup) and injected
into routes through FastAPI dependencies. Tests build a container with
fixture data, a temporary database, and in-memory vector storage instead of
patching globals.
"""

import logging
import threading
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from app.agents.coordinator import ResearchCoordinator
from app.core.config import Settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.session import Database
from app.knowledge.chunker import DocumentChunker
from app.knowledge.embeddings import ChromaDefaultEmbeddingProvider, HashEmbeddingProvider
from app.knowledge.model_cache import ModelPrefetcher
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import ChromaVectorStore
from app.llm.base import LLMProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.providers.base import MarketDataProvider
from app.providers.cache import CachingMarketDataProvider
from app.providers.fixture import FixtureMarketDataProvider
from app.providers.sec_edgar import SecEdgarClient
from app.providers.yahoo import YahooFinanceProvider
from app.services.analytics import AnalyticsService
from app.services.market_data import MarketDataService
from app.services.portfolio import PortfolioService
from app.services.technicals import TechnicalsService

logger = logging.getLogger("argus.container")


def build_market_data_provider(settings: Settings) -> MarketDataProvider:
    inner: MarketDataProvider
    if settings.market_data_provider == "fixture":
        inner = FixtureMarketDataProvider()
    else:
        inner = YahooFinanceProvider(
            timeout_seconds=settings.provider_timeout_seconds,
            request_timeout_seconds=settings.provider_request_timeout_seconds,
            max_attempts=settings.provider_max_attempts,
            retry_base_seconds=settings.provider_retry_base_seconds,
            max_concurrency=settings.provider_max_concurrency,
        )
    return CachingMarketDataProvider(
        inner,
        max_entries=settings.cache_max_entries,
        max_stale_seconds=settings.cache_max_stale_seconds,
    )


def build_llm(settings: Settings) -> LLMProvider | None:
    """Only free, local model servers are supported (see app.llm)."""
    if not settings.llm_enabled:
        return None
    return OpenAICompatibleProvider(
        model=settings.llm_model or "",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.llm_max_attempts,
        allow_remote=settings.llm_allow_remote,
    )


def build_retriever(settings: Settings) -> KnowledgeRetriever:
    embeddings = (
        HashEmbeddingProvider(256)
        if settings.embedding_provider == "hash"
        else ChromaDefaultEmbeddingProvider()
    )
    store = ChromaVectorStore(
        embedding_provider=embeddings,
        path=settings.resolved_chroma_path,
        # One collection per embedding space: vectors from different models are
        # not comparable, so switching providers must never mix them.
        collection_name=f"{settings.knowledge_collection_name}_{embeddings.tag}",
    )
    return KnowledgeRetriever(
        store,
        DocumentChunker(settings.knowledge_chunk_size, settings.knowledge_chunk_overlap),
        min_score=settings.knowledge_min_score,
    )


class Container:
    def __init__(
        self,
        settings: Settings,
        provider: MarketDataProvider | None = None,
        database: Database | None = None,
        retriever_factory: Callable[[], KnowledgeRetriever] | None = None,
        llm: LLMProvider | None = None,
        use_configured_llm: bool = True,
        sec: SecEdgarClient | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider or build_market_data_provider(settings)
        self.market = MarketDataService(self.provider)
        self.analytics = AnalyticsService(self.market, settings.quant_benchmark_ticker)
        self.portfolios = PortfolioService(self.market, settings.quant_benchmark_ticker)
        self.technicals = TechnicalsService(self.market)
        self.database = database or Database(settings.resolved_database_url)
        self.llm = llm if llm is not None or not use_configured_llm else build_llm(settings)
        self.sec = sec or (SecEdgarClient(settings.sec_user_agent) if settings.sec_user_agent else None)
        self.files_dir: Path = settings.data_dir / "uploads"
        self.session_ttl = timedelta(hours=settings.session_ttl_hours)
        self.auth_limiter = SlidingWindowRateLimiter(settings.auth_rate_limit_per_minute, 60)
        self.research_limiter = SlidingWindowRateLimiter(settings.research_rate_limit_per_minute, 60)
        self.api_limiter = SlidingWindowRateLimiter(settings.api_rate_limit_per_minute, 60)
        self.upload_limiter = SlidingWindowRateLimiter(settings.upload_rate_limit_per_minute, 60)
        # Login attempts per IP across all emails (password spraying).
        self.login_ip_limiter = SlidingWindowRateLimiter(settings.auth_rate_limit_per_minute * 3, 60)
        self._retriever_factory = retriever_factory or (lambda: build_retriever(settings))
        self._retriever: KnowledgeRetriever | None = None
        self.embedding_prefetcher = ModelPrefetcher() if settings.embedding_provider == "onnx" else None
        self._retriever_lock = threading.Lock()

    def retriever(self) -> KnowledgeRetriever:
        """Built lazily: loading the ONNX embedding model takes a few seconds
        and is unnecessary for market-only workflows."""
        if self._retriever is None:
            with self._retriever_lock:
                if self._retriever is None:
                    self._retriever = self._retriever_factory()
        return self._retriever

    @property
    def retriever_loaded(self) -> bool:
        return self._retriever is not None

    def coordinator(self, with_documents: bool) -> ResearchCoordinator:
        return ResearchCoordinator(
            market_data=self.market,
            analytics=self.analytics,
            retriever=self.retriever() if with_documents else None,
            llm=self.llm,
            retrieval_limit=self.settings.knowledge_retrieval_limit,
            llm_max_output_tokens=self.settings.llm_max_output_tokens,
        )
