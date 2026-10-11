"""Injectable local embedding implementations."""

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

from app.core.errors import DependencyUnavailableError


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed document text."""

    def embed_query(self, text: str) -> list[float]:
        """Embed one retrieval query."""


class EmbeddingModelUnavailableError(DependencyUnavailableError):
    code = "embedding_model_unavailable"


class ChromaDefaultEmbeddingProvider:
    """Chroma's local ONNX all-MiniLM-L6-v2 (384 dimensions).

    The model files are fetched by :mod:`app.knowledge.model_cache`, never by
    Chroma's own downloader; until they are present, embedding fails fast with
    an actionable error instead of hanging on a slow download."""

    tag = "minilm"

    def __init__(self, ready=None) -> None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        from app.knowledge.model_cache import model_ready

        self._ready = ready or model_ready
        self._function = DefaultEmbeddingFunction()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not self._ready():
            raise EmbeddingModelUnavailableError(
                "The local embedding model (all-MiniLM-L6-v2, ~80 MB) is not downloaded yet. "
                "It downloads in the background; check /api/system/status, run "
                "`python -m app.knowledge.model_cache`, or set ARGUS_EMBEDDING_PROVIDER=hash."
            )
        return [_plain_floats(vector) for vector in self._function(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class HashEmbeddingProvider:
    """Deterministic hashed bag-of-words embedding: no download, works offline,
    purely lexical (no semantic similarity). For tests and slow networks."""

    def __init__(self, dimensions: int = 128) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8.")
        self._dimensions = dimensions
        self.tag = f"hash{dimensions}"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self._dimensions
            vector[index] += -1.0 if value & 1 else 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


def _plain_floats(vector) -> list[float]:
    """Convert a numpy vector to plain Python floats. ``list(ndarray)`` would
    yield ``np.float32`` scalars, which Chroma rejects on upsert."""
    values = vector.tolist() if hasattr(vector, "tolist") else vector
    return [float(x) for x in values]
