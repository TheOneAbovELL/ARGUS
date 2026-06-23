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

    model_config = SettingsConfigDict(env_prefix="ARGUS_")


settings = Settings()
