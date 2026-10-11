"""Research routes: run (JSON or streamed progress) and saved history.

Streaming uses Server-Sent Events over a POST response. It is justified by
latency, not novelty: a run with a local LLM can take tens of seconds and
the user should see which stage is executing. Without an LLM the stream
finishes almost immediately and the JSON endpoint is equivalent.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import ContainerDep, CurrentUser, DbDep, OptionalUser, client_key
from app.core.errors import ArgusError, error_body
from app.db.models import User
from app.providers.models import normalize_symbol
from app.repositories.workspace import DocumentRepository, ResearchRepository
from app.schemas.common import PageMeta
from app.schemas.research import ResearchList, ResearchOut, ResearchRequest, ResearchSummaryOut

logger = logging.getLogger("argus.api.research")
router = APIRouter(prefix="/api/research", tags=["research"])


def _check_rate(container, request: Request, user: User | None) -> None:
    container.research_limiter.check(client_key(request, user), "Research rate limit reached; try again shortly.")


async def _run(
    body: ResearchRequest,
    request: Request,
    container,
    db,
    user: User | None,
    on_event=None,
) -> ResearchOut:
    symbol = normalize_symbol(body.symbol)
    document_ids: list[str] = []
    if user is not None:
        document_ids = await DocumentRepository(db, user.id).ready_ids(symbol)
    coordinator = await asyncio.to_thread(container.coordinator, bool(document_ids))
    report = await coordinator.research(
        symbol,
        question=body.question,
        owner_id=user.id if user else None,
        document_ids=document_ids,
        period=body.period,
        on_event=on_event,
    )
    out = ResearchOut(**report.model_dump())
    if user is not None and body.save:
        record = await ResearchRepository(db, user.id).save(
            symbol, report.question, report.generation.mode, report.generation.model, report.model_dump(mode="json")
        )
        out.id, out.saved = record.id, True
    return out


@router.post("", response_model=ResearchOut)
async def research(body: ResearchRequest, request: Request, container: ContainerDep, db: DbDep, user: OptionalUser):
    _check_rate(container, request, user)
    return await _run(body, request, container, db, user)


@router.post("/stream", summary="Run research with Server-Sent Events progress")
async def research_stream(
    body: ResearchRequest, request: Request, container: ContainerDep, db: DbDep, user: OptionalUser
) -> StreamingResponse:
    _check_rate(container, request, user)
    normalize_symbol(body.symbol)  # fail fast with a normal 400 before streaming starts
    queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()

    async def on_event(event: dict) -> None:
        await queue.put(("step", event))

    async def worker() -> None:
        try:
            # Request-scoped dependencies are closed before a streaming body
            # runs, so the worker owns its own session.
            async with container.database.sessionmaker() as session:
                out = await _run(body, request, container, session, user, on_event)
            await queue.put(("report", out.model_dump(mode="json")))
        except ArgusError as exc:
            await queue.put(("error", error_body(exc.code, exc.message, exc.details)))
        except Exception:
            logger.exception("streamed research failed")
            await queue.put(("error", error_body("internal_error", "Research failed unexpectedly.")))
        finally:
            await queue.put(None)

    async def stream():
        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event, payload = item
                yield f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
        finally:
            if not task.done():  # client disconnected: stop the work
                task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=ResearchList)
async def list_research(
    user: CurrentUser,
    db: DbDep,
    symbol: str | None = Query(None, max_length=16),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    page = await ResearchRepository(db, user.id).list(limit, offset, normalize_symbol(symbol) if symbol else None)
    return ResearchList(
        items=[ResearchSummaryOut.of(r) for r in page.items],
        page=PageMeta(total=page.total, limit=limit, offset=offset),
    )


@router.get("/{report_id}", response_model=ResearchOut)
async def get_research(report_id: str, user: CurrentUser, db: DbDep):
    record = await ResearchRepository(db, user.id).get(report_id)
    return ResearchOut(**record.report, id=record.id, saved=True)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_research(report_id: str, user: CurrentUser, db: DbDep) -> Response:
    await ResearchRepository(db, user.id).delete(report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
