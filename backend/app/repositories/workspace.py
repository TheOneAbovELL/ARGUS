"""Owner-scoped persistence for workspace objects.

Every repository is constructed with the authenticated user's id and applies
it to *every* query. There is deliberately no method that reads another
user's rows: a resource owned by someone else is indistinguishable from one
that does not exist (404), which avoids leaking existence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import ConflictError, NotFoundError
from app.db.models import (
    Document,
    Portfolio,
    PortfolioHolding,
    ResearchReport,
    WatchlistItem,
    utcnow,
)


@dataclass(frozen=True)
class Page:
    items: list
    total: int
    limit: int
    offset: int


class _OwnedRepository:
    def __init__(self, session: AsyncSession, owner_id: str) -> None:
        self._db = session
        self._owner = owner_id


class PortfolioRepository(_OwnedRepository):
    async def list(self, limit: int, offset: int) -> Page:
        query = select(Portfolio).where(Portfolio.owner_id == self._owner)
        total = await self._db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self._db.scalars(
            query.order_by(Portfolio.updated_at.desc()).limit(limit).offset(offset)
        )
        return Page(list(rows), total or 0, limit, offset)

    async def get(self, portfolio_id: str) -> Portfolio:
        portfolio = await self._db.scalar(
            select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.owner_id == self._owner)
        )
        if portfolio is None:
            raise NotFoundError("Portfolio not found.")
        return portfolio

    async def create(
        self,
        name: str,
        description: str | None,
        benchmark: str,
        rebalancing: str,
        holdings: Sequence[tuple[str, float]],
    ) -> Portfolio:
        portfolio = Portfolio(
            owner_id=self._owner,
            name=name,
            description=description,
            benchmark=benchmark,
            rebalancing=rebalancing,
            holdings=_holdings(holdings),
        )
        self._db.add(portfolio)
        await self._commit_unique("A portfolio with this name already exists.")
        return portfolio

    async def update(
        self,
        portfolio_id: str,
        expected_version: int,
        name: str,
        description: str | None,
        benchmark: str,
        rebalancing: str,
        holdings: Sequence[tuple[str, float]],
    ) -> Portfolio:
        portfolio = await self.get(portfolio_id)
        if portfolio.version != expected_version:
            raise ConflictError(
                "This portfolio was modified elsewhere. Reload it and apply your changes again.",
                details={"current_version": portfolio.version},
            )
        portfolio.name = name
        portfolio.description = description
        portfolio.benchmark = benchmark
        portfolio.rebalancing = rebalancing
        portfolio.updated_at = utcnow()  # always UPDATE the row so the version bumps
        portfolio.holdings.clear()
        # The parent UPDATE (unique name, version check) fires at this flush,
        # so it needs the same conflict handling as the commit.
        await self._guarded(self._db.flush(), "A portfolio with this name already exists.")
        portfolio.holdings.extend(_holdings(holdings))
        await self._guarded(self._db.commit(), "A portfolio with this name already exists.")
        await self._db.refresh(portfolio)
        return portfolio

    async def delete(self, portfolio_id: str) -> None:
        portfolio = await self.get(portfolio_id)
        await self._db.delete(portfolio)
        await self._db.commit()

    async def _commit_unique(self, message: str) -> None:
        await self._guarded(self._db.commit(), message)

    async def _guarded(self, operation, message: str) -> None:
        try:
            await operation
        except IntegrityError as exc:
            await self._db.rollback()
            raise ConflictError(message) from exc
        except StaleDataError as exc:
            await self._db.rollback()
            raise ConflictError("This portfolio was modified concurrently. Reload and retry.") from exc


def _holdings(holdings: Sequence[tuple[str, float]]) -> list[PortfolioHolding]:
    return [
        PortfolioHolding(symbol=symbol, weight=weight, position=index)
        for index, (symbol, weight) in enumerate(holdings)
    ]


class WatchlistRepository(_OwnedRepository):
    MAX_ITEMS = 100

    async def list(self) -> list[WatchlistItem]:
        rows = await self._db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.owner_id == self._owner)
            .order_by(WatchlistItem.created_at)
        )
        return list(rows)

    async def add(self, symbol: str) -> WatchlistItem:
        existing = await self._db.scalar(
            select(WatchlistItem).where(
                WatchlistItem.owner_id == self._owner, WatchlistItem.symbol == symbol
            )
        )
        if existing is not None:  # idempotent: adding twice is not an error
            return existing
        count = await self._db.scalar(
            select(func.count()).where(WatchlistItem.owner_id == self._owner)
        )
        if (count or 0) >= self.MAX_ITEMS:
            raise ConflictError(f"Watchlists are limited to {self.MAX_ITEMS} symbols.")
        item = WatchlistItem(owner_id=self._owner, symbol=symbol)
        self._db.add(item)
        try:
            await self._db.commit()
        except IntegrityError:  # concurrent duplicate insert
            await self._db.rollback()
            return await self.add(symbol)
        return item

    async def remove(self, symbol: str) -> None:
        result = await self._db.execute(
            delete(WatchlistItem).where(
                WatchlistItem.owner_id == self._owner, WatchlistItem.symbol == symbol
            )
        )
        await self._db.commit()
        if result.rowcount == 0:
            raise NotFoundError(f"'{symbol}' is not on your watchlist.")


class ResearchRepository(_OwnedRepository):
    async def save(
        self, symbol: str, question: str | None, mode: str, model: str | None, report: dict
    ) -> ResearchReport:
        record = ResearchReport(
            owner_id=self._owner,
            symbol=symbol,
            question=question,
            generation_mode=mode,
            model=model,
            report=report,
        )
        self._db.add(record)
        await self._db.commit()
        return record

    async def list(self, limit: int, offset: int, symbol: str | None = None) -> Page:
        query = select(ResearchReport).where(ResearchReport.owner_id == self._owner)
        if symbol:
            query = query.where(ResearchReport.symbol == symbol)
        total = await self._db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self._db.scalars(
            query.order_by(ResearchReport.created_at.desc()).limit(limit).offset(offset)
        )
        return Page(list(rows), total or 0, limit, offset)

    async def get(self, report_id: str) -> ResearchReport:
        record = await self._db.scalar(
            select(ResearchReport).where(
                ResearchReport.id == report_id, ResearchReport.owner_id == self._owner
            )
        )
        if record is None:
            raise NotFoundError("Research report not found.")
        return record

    async def delete(self, report_id: str) -> None:
        record = await self.get(report_id)
        await self._db.delete(record)
        await self._db.commit()


class DocumentRepository(_OwnedRepository):
    async def find_by_source(self, source: str) -> Document | None:
        return await self._db.scalar(
            select(Document).where(Document.owner_id == self._owner, Document.source == source)
        )

    async def find_by_hash(self, sha256: str) -> Document | None:
        return await self._db.scalar(
            select(Document).where(
                Document.owner_id == self._owner, Document.content_sha256 == sha256
            )
        )

    async def create(
        self,
        symbol: str,
        title: str,
        document_type: str,
        source: str,
        filename: str | None,
        sha256: str,
        size_bytes: int,
        published_on: date | None,
    ) -> Document:
        document = Document(
            owner_id=self._owner,
            symbol=symbol,
            title=title,
            document_type=document_type,
            source=source,
            filename=filename,
            content_sha256=sha256,
            size_bytes=size_bytes,
            published_on=published_on,
            status="processing",
        )
        self._db.add(document)
        try:
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise ConflictError("You have already uploaded this exact document.") from exc
        return document

    async def mark(
        self,
        document: Document,
        status: str,
        page_count: int = 0,
        chunk_count: int = 0,
        error: str | None = None,
    ) -> Document:
        document.status = status
        document.page_count = page_count
        document.chunk_count = chunk_count
        document.error = error
        await self._db.commit()
        return document

    async def list(self, limit: int, offset: int, symbol: str | None = None) -> Page:
        query = select(Document).where(Document.owner_id == self._owner)
        if symbol:
            query = query.where(Document.symbol == symbol)
        total = await self._db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self._db.scalars(
            query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        )
        return Page(list(rows), total or 0, limit, offset)

    async def get(self, document_id: str) -> Document:
        document = await self._db.scalar(
            select(Document).where(Document.id == document_id, Document.owner_id == self._owner)
        )
        if document is None:
            raise NotFoundError("Document not found.")
        return document

    async def ready_ids(self, symbol: str | None = None) -> list[str]:
        query = select(Document.id).where(
            Document.owner_id == self._owner, Document.status == "ready"
        )
        if symbol:
            query = query.where(Document.symbol == symbol)
        return list(await self._db.scalars(query))

    async def delete(self, document: Document) -> None:
        await self._db.delete(document)
        await self._db.commit()
