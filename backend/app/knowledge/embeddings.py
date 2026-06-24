"""Injectable local embedding implementations."""

from collections.abc import Sequence
import hashlib
import math
import re
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed document text."""

    def embed_query(self, text: str) -> list[float]:
        """Embed one retrieval query."""


class ChromaDefaultEmbeddingProvider:
    """Use Chroma's local ONNX MiniLM embedding function."""

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        self._function = DefaultEmbeddingFunction()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(vector) for vector in self._function(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class HashEmbeddingProvider:
    """Small deterministic bag-of-words embedding for offline tests."""

    def __init__(self, dimensions: int = 128) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8.")
        self._dimensions = dimensions

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
