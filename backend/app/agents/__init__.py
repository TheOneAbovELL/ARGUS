"""Specialist research agents and the orchestration that grounds them.

Market, Risk, News, Document, and Strategy agents are deterministic and read
only from the evidence ledger; optional LLM synthesis rewrites their findings
and is held to the same validation rules.
"""

from app.agents.coordinator import ResearchCoordinator

__all__ = ["ResearchCoordinator"]
