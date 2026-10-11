"""Typed research-report structures shared by agents, synthesis, and the API.

A report is a set of sections, each a list of *claims*. Every claim states
its kind — ``fact`` (directly supported by cited evidence) or
``interpretation`` (analysis built on cited evidence, labelled as such) —
and the evidence ids it relies on. Nothing reaches the user without passing
the validator in :mod:`app.agents.validation`.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ClaimKind(StrEnum):
    FACT = "fact"
    INTERPRETATION = "interpretation"


class Claim(BaseModel):
    text: str
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list)
    # "agent": written by ARGUS's rule-based agents; "model": proposed by the
    # language model. Both pass the same validator.
    origin: str = "agent"


class Section(BaseModel):
    key: str
    title: str
    claims: list[Claim] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    id: str
    kind: str  # quote | profile | metric | news | document
    label: str
    statement: str
    source: str
    as_of: str | None = None
    value: float | None = None
    unit: str | None = None
    url: str | None = None
    document_id: str | None = None
    page_number: int | None = None
    chunk_id: str | None = None
    retrieval_score: float | None = None
    untrusted: bool = False  # third-party text (headlines, documents)


class RejectedClaim(BaseModel):
    section: str
    text: str
    reasons: list[str]


class ValidationSummary(BaseModel):
    claims_total: int = 0
    claims_accepted: int = 0
    claims_rejected: int = 0
    # Rule-based claims shown in an LLM report where the model's section was
    # empty; not counted in the totals above, which describe model output.
    claims_backfilled: int = 0
    rejected: list[RejectedClaim] = Field(default_factory=list)


class GenerationInfo(BaseModel):
    mode: str  # deterministic | llm
    provider: str | None = None
    model: str | None = None
    fallback_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    validation: ValidationSummary = Field(default_factory=ValidationSummary)


class TraceStep(BaseModel):
    step: str
    status: str  # ok | partial | failed | skipped
    duration_ms: float
    detail: str | None = None


class ResearchReport(BaseModel):
    symbol: str
    name: str | None = None
    question: str | None = None
    generated_at: str
    window: dict
    sections: list[Section]
    scenarios: list[Section]
    evidence: list[EvidenceItem]
    limitations: list[str]
    generation: GenerationInfo
    trace: list[TraceStep]
    disclaimer: str = (
        "ARGUS is a research tool, not investment advice. Historical metrics do not "
        "predict future returns; data may be delayed or incomplete."
    )
