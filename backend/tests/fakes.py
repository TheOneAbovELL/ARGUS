"""Scripted stand-ins for the language model (no network, no cost)."""

from collections.abc import Callable
from typing import Any

from app.llm.base import LLMResult


class ScriptedLLM:
    """Returns whatever ``script(user_prompt)`` produces, recording calls."""

    name = "scripted"
    model = "scripted-model"

    def __init__(self, script: Callable[[str], dict[str, Any]] | Exception) -> None:
        self._script = script
        self.calls: list[str] = []

    async def generate_json(self, system: str, user: str, schema: dict, max_output_tokens: int) -> LLMResult:
        self.calls.append(user)
        if isinstance(self._script, Exception):
            raise self._script
        return LLMResult(data=self._script(user), model=self.model, input_tokens=100, output_tokens=50)


def empty_sections() -> dict[str, list]:
    return {k: [] for k in ("summary", "market", "risk", "news", "documents", "answer", "bull", "base", "bear")}
