"""Health, readiness, system status, and metric definitions."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import ContainerDep
from app.quant.definitions import METRIC_DEFINITIONS

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    """The process is up. Deliberately checks nothing external."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def ready(container: ContainerDep) -> JSONResponse:
    """Dependencies required to serve requests. Reports component status only
    (no connection strings, versions, or error text)."""
    database_ok = await container.database.ping()
    checks = {"database": "ok" if database_ok else "unavailable"}
    if container.retriever_loaded:
        try:
            await asyncio.to_thread(container.retriever().count)
            checks["vector_store"] = "ok"
        except Exception:
            checks["vector_store"] = "unavailable"
    else:
        checks["vector_store"] = "not_loaded"
    healthy = all(value in ("ok", "not_loaded") for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )


@router.get("/api/system/status", summary="Configured capabilities")
async def status(container: ContainerDep) -> dict:
    settings = container.settings
    return {
        "version": settings.app_version,
        "environment": settings.environment,
        "market_data": {
            "provider": container.provider.name,
            "mode": "fixture" if settings.market_data_provider == "fixture" else "delayed",
            "note": (
                "Synthetic fixture data — not market prices."
                if settings.market_data_provider == "fixture"
                else "Free Yahoo Finance data via yfinance: unofficial and possibly delayed; not real-time."
            ),
        },
        "research": {
            "mode": "llm" if container.llm is not None else "deterministic",
            "llm_provider": container.llm.name if container.llm else None,
            "llm_model": container.llm.model if container.llm else None,
            "llm_host": getattr(container.llm, "host", None) if container.llm else None,
            "llm_local": getattr(container.llm, "is_local", None) if container.llm else None,
        },
        "embeddings": _embeddings_status(container),
        "sec_edgar": container.sec is not None,
    }


def _embeddings_status(container) -> dict:
    prefetcher = container.embedding_prefetcher
    if prefetcher is None:
        return {"provider": "hash", "ready": True, "status": "ready", "note": "Lexical hash embeddings (offline)."}
    state = prefetcher.state
    return {
        "provider": "onnx",
        "ready": state.status == "ready",
        "status": state.status,
        "downloaded_mb": round(state.downloaded_bytes / 1e6, 1),
        "total_mb": round(state.total_bytes / 1e6, 1) if state.total_bytes else None,
        "note": (
            None
            if state.status == "ready"
            else "Document upload and search need the local embedding model (~80 MB download)."
        ),
    }


@router.get("/api/meta/metrics", summary="Metric definitions and conventions")
async def metric_definitions() -> list[dict[str, str]]:
    return METRIC_DEFINITIONS
