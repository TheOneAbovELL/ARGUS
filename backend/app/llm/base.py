"""Provider-neutral LLM contract.

The research pipeline only ever asks a model for one thing: a JSON object that
conforms to a JSON Schema, given a trusted system prompt and a user message
that contains (clearly delimited) untrusted evidence. Keeping the interface
this narrow keeps model-specific code out of business logic and makes the
model trivially replaceable by a scripted fake in tests and evals.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.errors import ArgusError, ModelUnavailableError


class ModelOutputError(ArgusError):
    """The model answered, but the answer is unusable (refusal, truncation,
    invalid JSON). Distinct from the model being unreachable."""

    status_code = 502
    code = "model_output_invalid"


__all__ = ["LLMProvider", "LLMResult", "ModelOutputError", "ModelUnavailableError"]


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> LLMResult: ...
