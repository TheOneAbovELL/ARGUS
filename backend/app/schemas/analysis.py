"""Request and response schemas for ticker analysis endpoints."""

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    """Client request body for analyzing a single stock ticker."""

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Stock ticker symbol to analyze.",
        examples=["NVDIA"],
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        """Normalize ticker symbols before route logic receives them."""
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be blank")
        if not normalized.isalnum():
            raise ValueError("ticker must contain only letters and numbers")
        return normalized


class AnalyzeResponse(BaseModel):
    """Structured response returned by the ticker analysis endpoint."""

    ticker: str
    company_name: str
    sector: str
    current_price: float

