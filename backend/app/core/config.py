"""Application configuration for the ARGUS backend."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the FastAPI application."""

    app_name: str = "ARGUS API"
    app_version: str = "0.1.0"
    market_data_provider: Literal["yfinance", "mock"] = "yfinance"
    yfinance_max_attempts: int = 2
    yfinance_retry_delay_seconds: float = 0.25
    quant_benchmark_ticker: str = "SPY"
    quant_history_period: str = "1y"
    quant_annual_risk_free_rate: float = 0.0
    knowledge_chroma_path: str = ".argus/chroma"
    knowledge_collection_name: str = "argus_knowledge"
    knowledge_chunk_size: int = 250
    knowledge_chunk_overlap: int = 40
    knowledge_retrieval_limit: int = 3

    model_config = SettingsConfigDict(env_prefix="ARGUS_")


settings = Settings()
