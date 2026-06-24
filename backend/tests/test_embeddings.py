"""Tests for deterministic offline embeddings."""

import math

import pytest

from app.knowledge.embeddings import HashEmbeddingProvider


def test_hash_embeddings_are_normalized_and_repeatable() -> None:
    provider = HashEmbeddingProvider(dimensions=64)
    first = provider.embed_query("revenue growth and guidance")
    second = provider.embed_query("revenue growth and guidance")

    assert first == second
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)
