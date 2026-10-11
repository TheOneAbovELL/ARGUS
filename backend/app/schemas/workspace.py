"""Auth, watchlist, and document contracts."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.db.models import Document, User, WatchlistItem
from app.knowledge.vector_store import RetrievedChunk
from app.schemas.common import PageMeta


class SignupIn(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=256)
    display_name: str | None = Field(None, max_length=80)


class LoginIn(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=256)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    created_at: datetime

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at)


class SessionOut(BaseModel):
    user: UserOut
    expires_at: datetime
    token: str | None = Field(
        None, description="Returned only when requested for API clients; browsers use the cookie."
    )


class WatchlistIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)


class WatchlistItemOut(BaseModel):
    symbol: str
    created_at: datetime

    @classmethod
    def of(cls, item: WatchlistItem) -> "WatchlistItemOut":
        return cls(symbol=item.symbol, created_at=item.created_at)


class DocumentOut(BaseModel):
    id: str
    symbol: str
    title: str
    document_type: str
    source: str
    filename: str | None
    size_bytes: int
    page_count: int
    chunk_count: int
    status: str
    error: str | None
    published_on: date | None
    created_at: datetime

    @classmethod
    def of(cls, doc: Document) -> "DocumentOut":
        return cls(
            id=doc.id,
            symbol=doc.symbol,
            title=doc.title,
            document_type=doc.document_type,
            source=doc.source,
            filename=doc.filename,
            size_bytes=doc.size_bytes,
            page_count=doc.page_count,
            chunk_count=doc.chunk_count,
            status=doc.status,
            error=doc.error,
            published_on=doc.published_on,
            created_at=doc.created_at,
        )


class DocumentList(BaseModel):
    items: list[DocumentOut]
    page: PageMeta


class DocumentSearchIn(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    symbol: str | None = Field(None, max_length=16)
    limit: int = Field(5, ge=1, le=20)


class PassageOut(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    document_type: str
    source: str
    page_number: int
    text: str
    score: float
    dense_score: float
    lexical_score: float
    published_on: date | None

    @classmethod
    def of(cls, chunk: RetrievedChunk) -> "PassageOut":
        return cls(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            title=chunk.title,
            document_type=chunk.document_type.value,
            source=chunk.source,
            page_number=chunk.page_number,
            text=chunk.text,
            score=round(chunk.score, 4),
            dense_score=round(chunk.dense_score, 4),
            lexical_score=round(chunk.lexical_score, 4),
            published_on=chunk.published_on,
        )


class DocumentSearchOut(BaseModel):
    query: str
    passages: list[PassageOut]
    insufficient_evidence: bool


class FilingOut(BaseModel):
    form: str
    accession: str
    filed_on: date
    report_date: date | None
    company: str
    url: str


class SecImportIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    accession: str = Field(..., min_length=20, max_length=20, examples=["0000320193-24-000123"])
