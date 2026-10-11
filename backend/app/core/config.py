"""Application configuration for the ARGUS backend.

All settings are read from environment variables prefixed with ``ARGUS_`` (and
from ``backend/.env`` when present). Secrets such as LLM API keys are held as
``SecretStr`` so they never appear in logs, reprs, or API responses.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_DATA_DIR = (
    Path("/tmp/.argus") if os.environ.get("VERCEL") else BACKEND_DIR / ".argus"
)


class Settings(BaseSettings):
    """Runtime settings for the FastAPI application."""

    app_name: str = "ARGUS API"
    app_version: str = "0.2.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = False

    # ── HTTP ────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    max_request_bytes: int = 1_000_000
    max_upload_bytes: int = 15_000_000

    # ── Market data ─────────────────────────────────────────────────────
    market_data_provider: Literal["yfinance", "fixture"] = "yfinance"
    provider_request_timeout_seconds: float = 12.0  # per HTTP attempt
    provider_timeout_seconds: float = 45.0  # whole call, all attempts
    provider_max_attempts: int = 3
    provider_retry_base_seconds: float = 0.4
    # yfinance shares one curl_cffi session process-wide, and curl sessions are
    # not thread-safe: concurrent calls intermittently hung with 0 bytes
    # received, while sequential calls were as fast (measured 3.0s vs 3.5s for
    # four calls). Serialize by default.
    provider_max_concurrency: int = 1
    cache_max_entries: int = 2_000
    cache_max_stale_seconds: int = 24 * 3600

    # ── Quant defaults ──────────────────────────────────────────────────
    quant_benchmark_ticker: str = "SPY"
    quant_history_period: str = "1y"
    quant_annual_risk_free_rate: float = 0.0

    # ── Persistence ─────────────────────────────────────────────────────
    data_dir: Path = _DEFAULT_DATA_DIR
    database_url: str | None = None
    # Apply Alembic migrations on startup (convenient locally). Containers run
    # `alembic upgrade head` as an explicit step and set this to false.
    auto_migrate: bool = True

    # ── Auth ────────────────────────────────────────────────────────────
    session_ttl_hours: int = 24 * 7
    session_cookie_name: str = "argus_session"
    session_cookie_secure: bool = False
    # Interactive API docs (/docs, /openapi.json). Default: on, except in production.
    expose_api_docs: bool | None = None
    auth_rate_limit_per_minute: int = 10
    # Public routes that hit external data providers (market, analytics,
    # portfolio, filings), per client.
    api_rate_limit_per_minute: int = 120
    upload_rate_limit_per_minute: int = 10

    # ── Knowledge / RAG ─────────────────────────────────────────────────
    embedding_provider: Literal["onnx", "hash"] = "onnx"
    knowledge_chroma_path: Path | None = None
    knowledge_collection_name: str = "argus_knowledge"
    knowledge_chunk_size: int = 180
    knowledge_chunk_overlap: int = 30
    knowledge_retrieval_limit: int = 4
    knowledge_min_score: float = 0.15

    # ── SEC EDGAR (official filings) ────────────────────────────────────
    # The SEC requires a descriptive User-Agent with contact details. EDGAR
    # features stay disabled until one is configured.
    sec_user_agent: str | None = None

    # ── LLM (optional, free/local only) ─────────────────────────────────
    # Default "none": research uses the deterministic evidence-grounded
    # synthesizer and costs nothing. "openai_compatible" targets a *local*
    # model server (Ollama, LM Studio, llama.cpp). Remote endpoints are refused
    # unless llm_allow_remote is explicitly enabled, so a paid API cannot be
    # used by accident.
    llm_provider: Literal["none", "openai_compatible"] = "none"
    llm_model: str | None = None
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: SecretStr | None = None
    llm_allow_remote: bool = False
    llm_timeout_seconds: float = 120.0
    llm_max_output_tokens: int = 2_500
    llm_max_attempts: int = 3
    research_rate_limit_per_minute: int = 12

    model_config = SettingsConfigDict(
        env_prefix="ARGUS_",
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard_origin(cls, value: list[str]) -> list[str]:
        # Credentials are allowed, so a wildcard would reflect any Origin.
        if any(origin.strip() == "*" for origin in value):
            raise ValueError("ARGUS_CORS_ORIGINS must list explicit origins; '*' is not allowed with cookies.")
        return value

    @field_validator("quant_annual_risk_free_rate")
    @classmethod
    def _rate_is_decimal(cls, value: float) -> float:
        # Same bounds as the API accepts; catches "4.5" meant as 4.5%.
        if not -0.05 <= value <= 0.25:
            raise ValueError("ARGUS_QUANT_ANNUAL_RISK_FREE_RATE must be an annual decimal between -0.05 and 0.25 (e.g. 0.045).")
        return value

    @field_validator("quant_benchmark_ticker")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{(self.data_dir / 'argus.db').as_posix()}"

    @property
    def resolved_chroma_path(self) -> Path:
        return self.knowledge_chroma_path or self.data_dir / "chroma"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "none" and bool(self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
