"""Shared response fragments."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.providers.models import Provenance


class ProvenanceOut(BaseModel):
    """Where a payload came from and how fresh it is."""

    provider: str
    mode: str  # delayed | end_of_day | fixture
    retrieved_at: datetime
    as_of: datetime | date | None = None
    cached: bool
    stale: bool

    @classmethod
    def of(cls, provenance: Provenance) -> "ProvenanceOut":
        return cls(
            provider=provenance.provider,
            mode=provenance.mode.value,
            retrieved_at=provenance.retrieved_at,
            as_of=provenance.as_of,
            cached=provenance.cached,
            stale=provenance.stale,
        )


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class WindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: date
    end: date
    label: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str | None = None
