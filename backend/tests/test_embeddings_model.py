"""Embedding-model prefetch and fail-fast behaviour (offline, mock transport)."""

import hashlib
import io
import tarfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.knowledge.embeddings import ChromaDefaultEmbeddingProvider, EmbeddingModelUnavailableError
from app.knowledge.model_cache import REQUIRED_FILES, ModelPrefetcher, model_ready
from tests.conftest import signup


def model_archive() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name in REQUIRED_FILES:
            data = f"fake {name}".encode()
            info = tarfile.TarInfo(f"onnx/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


ARCHIVE = model_archive()
DIGEST = hashlib.sha256(ARCHIVE).hexdigest()


def flaky_transport(fail_first_after: int | None = None, payload: bytes = ARCHIVE):
    """Serves ``payload``; honours Range; optionally drops the first connection."""
    calls = {"n": 0, "ranges": []}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        rng = request.headers.get("range")
        calls["ranges"].append(rng)
        start = int(rng.split("=")[1].rstrip("-")) if rng else 0
        body = payload[start:]
        if fail_first_after is not None and calls["n"] == 1:
            class Broken(httpx.SyncByteStream):
                def __iter__(self):
                    yield body[:fail_first_after]
                    raise httpx.ReadTimeout("stalled")

            return httpx.Response(200, stream=Broken(), headers={"content-length": str(len(body))})
        return httpx.Response(206 if rng else 200, content=body)

    return httpx.MockTransport(handler), calls


def test_prefetch_downloads_verifies_and_extracts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.model_cache.time.sleep", lambda s: None)
    transport, calls = flaky_transport(fail_first_after=100)
    prefetcher = ModelPrefetcher(root=tmp_path, sha256=DIGEST, transport=transport)
    assert prefetcher.ensure()
    assert model_ready(tmp_path) and prefetcher.state.status == "ready"
    assert calls["ranges"][1] == "bytes=100-"  # resumed instead of restarting


def test_prefetch_rejects_tampered_archive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.model_cache.time.sleep", lambda s: None)
    transport, _ = flaky_transport()
    prefetcher = ModelPrefetcher(root=tmp_path, sha256="0" * 64, transport=transport)
    assert not prefetcher.ensure()
    assert prefetcher.state.status == "failed" and "SHA-256" in prefetcher.state.error
    assert not model_ready(tmp_path)


def test_prefetch_refuses_path_traversal(tmp_path: Path, monkeypatch) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    evil = buffer.getvalue()
    monkeypatch.setattr("app.knowledge.model_cache.time.sleep", lambda s: None)
    transport, _ = flaky_transport(payload=evil)
    prefetcher = ModelPrefetcher(root=tmp_path / "model", sha256=hashlib.sha256(evil).hexdigest(), transport=transport)
    assert not prefetcher.ensure()
    assert not (tmp_path / "escape.txt").exists()


def test_onnx_provider_fails_fast_when_model_missing() -> None:
    provider = ChromaDefaultEmbeddingProvider(ready=lambda: False)
    with pytest.raises(EmbeddingModelUnavailableError, match="ARGUS_EMBEDDING_PROVIDER=hash"):
        provider.embed_documents(["text"])


def test_upload_reports_missing_model_clearly(client: TestClient, container) -> None:
    signup(client)
    retriever = container.retriever()

    async def not_ready(document):
        raise EmbeddingModelUnavailableError("The local embedding model is not downloaded yet.")

    retriever.ingest = not_ready
    response = client.post("/api/documents", files={"file": ("a.txt", b"Revenue grew.", "text/plain")}, data={"symbol": "NVDA"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "embedding_model_unavailable"
    assert client.get("/api/documents").json()["page"]["total"] == 0  # rolled back


def test_status_reports_embedding_readiness(client: TestClient) -> None:
    embeddings = client.get("/api/system/status").json()["embeddings"]
    assert embeddings == {"provider": "hash", "ready": True, "status": "ready", "note": "Lexical hash embeddings (offline)."}


def test_onnx_provider_returns_plain_floats_that_chroma_accepts() -> None:
    import chromadb
    import numpy as np

    provider = ChromaDefaultEmbeddingProvider(ready=lambda: True)
    provider._function = lambda texts: [np.array([0.1, 0.2, 0.3], dtype=np.float32) for _ in texts]
    vectors = provider.embed_documents(["a", "b"])
    assert all(type(x) is float for v in vectors for x in v)
    collection = chromadb.EphemeralClient().get_or_create_collection("plain_float_check")
    collection.upsert(ids=["1", "2"], documents=["a", "b"], embeddings=vectors)  # must not raise
    assert collection.count() == 2
