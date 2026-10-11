"""Research orchestration: an explicit, bounded, staged pipeline.

    validate → gather (parallel) → retrieve → build evidence → specialist
    agents → synthesis (LLM, optional) → validation → report

Why a fixed pipeline instead of an autonomous agent loop: every research run
needs the same inputs, so letting a model choose tools would add cost,
latency, and failure modes without adding information. There are no
unbounded loops, no model-initiated tool calls, and at most one model call.

Degradation policy:
* Price history is required — without it there is nothing to analyse, so its
  errors propagate (unknown symbol, insufficient data, provider outage).
* Quote, profile, news, and document retrieval are optional; a failure is
  recorded in the trace and as a limitation, and the report continues.
* If the LLM is unavailable, returns invalid output, or too few of its claims
  survive validation, the deterministic report is used and the reason shown.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.agents.document_agent import DocumentAgent
from app.agents.evidence import EvidenceLedger
from app.agents.market_agent import MarketAgent
from app.agents.models import (
    Claim,
    ClaimKind,
    GenerationInfo,
    ResearchReport,
    Section,
    TraceStep,
    ValidationSummary,
)
from app.agents.news_agent import NewsAgent
from app.agents.risk_agent import RiskAgent
from app.agents.strategy_agent import StrategyAgent
from app.agents.synthesis import MAX_CLAIMS_PER_SECTION, synthesize
from app.agents.validation import validate_sections
from app.core.errors import ArgusError, InvalidRequestError
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import RetrievedChunk
from app.llm.base import LLMProvider
from app.providers.models import DataMode, normalize_symbol
from app.services.analytics import AnalyticsService
from app.services.market_data import MarketDataService

logger = logging.getLogger("argus.research")

EventSink = Callable[[dict[str, Any]], Awaitable[None]]
MAX_QUESTION_CHARS = 500
MIN_LLM_ACCEPTED_CLAIMS = 4
# Fail closed: if fewer than this share of the model's claims survive
# validation, the model is not trusted for this report at all.
MIN_LLM_ACCEPTANCE_RATIO = 0.6
DEFAULT_DOCUMENT_QUERY = "risk factors outlook guidance revenue growth competition"


class ResearchCoordinator:
    def __init__(
        self,
        market_data: MarketDataService,
        analytics: AnalyticsService,
        retriever: KnowledgeRetriever | None = None,
        llm: LLMProvider | None = None,
        retrieval_limit: int = 4,
        llm_max_output_tokens: int = 2_500,
        news_limit: int = 6,
    ) -> None:
        self._market = market_data
        self._analytics = analytics
        self._retriever = retriever
        self._llm = llm
        self._retrieval_limit = retrieval_limit
        self._llm_max_tokens = llm_max_output_tokens
        self._news_limit = news_limit
        self._market_agent = MarketAgent()
        self._risk_agent = RiskAgent()
        self._news_agent = NewsAgent()
        self._document_agent = DocumentAgent()
        self._strategy_agent = StrategyAgent()

    async def research(
        self,
        symbol: str,
        question: str | None = None,
        owner_id: str | None = None,
        document_ids: list[str] | None = None,
        period: str = "1y",
        on_event: EventSink | None = None,
    ) -> ResearchReport:
        symbol = normalize_symbol(symbol)
        question = (question or "").strip() or None
        if question and len(question) > MAX_QUESTION_CHARS:
            raise InvalidRequestError(f"Questions are limited to {MAX_QUESTION_CHARS} characters.")
        trace: list[TraceStep] = []
        limitations: list[str] = []

        async def step(name: str, status: str, started: float, detail: str | None = None) -> None:
            trace.append(TraceStep(step=name, status=status, duration_ms=round((time.perf_counter() - started) * 1000, 1), detail=detail))
            if on_event:
                await on_event({"type": "step", "step": name, "status": status, "detail": detail})

        # ── 1. gather market inputs concurrently ──────────────────────
        started = time.perf_counter()
        window = self._market.window(period)
        analysis_r, quote_r, profile_r, news_r = await asyncio.gather(
            self._analytics.analyze_asset(symbol, window),
            self._market.quote(symbol),
            self._market.profile(symbol),
            self._market.news(symbol, self._news_limit),
            return_exceptions=True,
        )
        if isinstance(analysis_r, BaseException):
            await step("market_data", "failed", started, getattr(analysis_r, "message", "analysis failed"))
            raise analysis_r
        analysis = analysis_r
        optional_failures = []
        for label, result in (("quote", quote_r), ("profile", profile_r), ("news", news_r)):
            if isinstance(result, ArgusError):
                optional_failures.append(label)
                limitations.append(f"The {label} could not be retrieved: {result.message}")
            elif isinstance(result, Exception):
                # Optional inputs never fail the whole report, even on a bug.
                logger.error("optional research input failed", exc_info=result, extra={"input": label})
                optional_failures.append(label)
                limitations.append(f"The {label} could not be retrieved because of an unexpected error.")
            elif isinstance(result, BaseException):
                raise result
        quote = None if isinstance(quote_r, BaseException) else quote_r
        profile = None if isinstance(profile_r, BaseException) else profile_r
        news = None if isinstance(news_r, BaseException) else news_r
        await step(
            "market_data",
            "partial" if optional_failures else "ok",
            started,
            f"{len(analysis.series.dates)} daily bars; unavailable: {', '.join(optional_failures)}"
            if optional_failures else f"{len(analysis.series.dates)} daily bars, quote, profile, news",
        )

        # ── 2. document retrieval (owner-scoped) ───────────────────────
        started = time.perf_counter()
        chunks: list[RetrievedChunk] = []
        question_chunk_ids: set[str] = set()
        if not owner_id:
            limitations.append("Sign in and upload documents to include filings or transcripts as evidence.")
            await step("documents", "skipped", started, "anonymous request")
        elif not self._retriever or not document_ids:
            limitations.append(f"No indexed documents for {symbol}; the report uses market data only.")
            await step("documents", "skipped", started, "no documents for this symbol")
        else:
            try:
                queries = [q for q in (question, DEFAULT_DOCUMENT_QUERY) if q]
                results = await asyncio.gather(
                    *(
                        self._retriever.retrieve(q, owner_id, symbol, self._retrieval_limit, document_ids=document_ids)
                        for q in queries
                    )
                )
                seen: set[str] = set()
                for index, batch in enumerate(results):
                    for chunk in batch:
                        if index == 0 and question:
                            question_chunk_ids.add(chunk.id)
                        if chunk.id not in seen:
                            seen.add(chunk.id)
                            chunks.append(chunk)
                if not chunks:
                    limitations.append("No document passage was relevant enough to cite (insufficient evidence).")
                await step("documents", "ok", started, f"{len(chunks)} passage(s) retrieved")
            except ArgusError as exc:
                limitations.append(f"Documents were not searched: {exc.message}")
                await step("documents", "failed", started, exc.code)
            except Exception:
                logger.exception("document retrieval failed")
                limitations.append("Document retrieval failed; the report uses market data only.")
                await step("documents", "failed", started, "retrieval error")

        # ── 3. evidence ledger ────────────────────────────────────────
        started = time.perf_counter()
        ledger = EvidenceLedger()
        conventions_id = ledger.add_conventions()
        quote_id = ledger.add_quote(quote) if quote else None
        profile_ids = ledger.add_profile(profile) if profile else []
        ledger.add_analysis(analysis)
        news_ids: list[str] = []
        if news is not None:
            # Prefer articles the provider tagged to this symbol; fall back to a
            # few untagged search results (labelled as such) only if none are.
            tagged = [n for n in news.items if symbol in n.related_symbols]
            chosen = tagged or list(news.items[:3])
            news_ids = [ledger.add_news(item, symbol, news.provenance) for item in chosen]
            if not news_ids:
                limitations.append("The news provider returned no recent headlines for this symbol.")
        document_ids_by_chunk = {chunk.id: ledger.add_document(chunk) for chunk in chunks}
        await step("evidence", "ok", started, f"{len(ledger.items())} evidence items")

        # ── 4. specialist agents (deterministic) ──────────────────────
        started = time.perf_counter()
        market_section = self._market_agent.analyze(analysis, ledger, quote_id, profile_ids, conventions_id)
        risk_section, risk_flags = self._risk_agent.analyze(analysis, ledger, conventions_id)
        news_section = self._news_agent.analyze(symbol, ledger, news_ids)
        doc_evidence = list(document_ids_by_chunk.values())
        documents_section = self._document_agent.analyze(ledger, doc_evidence)
        scenarios = self._strategy_agent.analyze(analysis, ledger, risk_flags, news_ids, doc_evidence)
        answer_ids = [document_ids_by_chunk[c.id] for c in chunks if c.id in question_chunk_ids]
        answer_section = Section(
            key="answer",
            title="Answer",
            # Passages retrieved for the question first, then the metrics it names.
            claims=[claim for claim in documents_section.claims if claim.evidence_ids[0] in answer_ids]
            + _metric_answer(question, ledger),
        )
        summary_section = _deterministic_summary(market_section, risk_flags, conventions_id)
        deterministic = [summary_section, market_section, risk_section, news_section, documents_section]
        if question:
            deterministic.append(answer_section)
        await step("agents", "ok", started, "market, risk, news, documents, strategy")

        # ── 5. synthesis + validation ─────────────────────────────────
        started = time.perf_counter()
        generation = GenerationInfo(mode="deterministic")
        summary = ValidationSummary()
        final_sections = validate_sections(deterministic, ledger, summary)
        final_scenarios = validate_sections(scenarios, ledger, summary)
        if question and self._llm is None:
            limitations.append(
                "No language model is configured, so the question is answered with the most relevant "
                "computed metrics and document passages rather than a written synthesis."
            )
            if not answer_section.claims:
                limitations.append("Nothing in the evidence directly addressed the question.")
        if self._llm is not None:
            if on_event:
                await on_event({"type": "step", "step": "synthesis", "status": "running", "detail": self._llm.model})
            try:
                llm_sections, parse_rejections, result = await synthesize(
                    self._llm, symbol, question, ledger, deterministic + scenarios, self._llm_max_tokens
                )
                llm_summary = ValidationSummary(
                    claims_total=len(parse_rejections),
                    claims_rejected=len(parse_rejections),
                    rejected=list(parse_rejections),
                )
                validated = validate_sections(
                    llm_sections, ledger, llm_summary, max_claims_per_section=MAX_CLAIMS_PER_SECTION
                )
                accepted, total = llm_summary.claims_accepted, llm_summary.claims_total
                if accepted < MIN_LLM_ACCEPTED_CLAIMS or accepted < MIN_LLM_ACCEPTANCE_RATIO * total:
                    raise _InsufficientSynthesis(
                        f"only {accepted} of {total} model claims passed validation"
                    )
                by_key = {s.key: s for s in validated}
                # Where the model left a section empty but the deterministic
                # agents had validated findings, keep those findings rather than
                # showing a thinner report.
                fallback = {s.key: s for s in final_sections + final_scenarios}
                filled = [
                    key for key, section in by_key.items()
                    if not section.claims and fallback.get(key) is not None and fallback[key].claims
                ]
                for key in filled:
                    by_key[key] = fallback[key]
                llm_summary.claims_backfilled = sum(len(fallback[key].claims) for key in filled)
                if filled:
                    limitations.append(
                        "These sections show ARGUS's rule-based findings because the language model "
                        f"provided no valid claims for them: {', '.join(filled)}."
                    )
                trimmed = sorted({r.section for r in llm_summary.rejected})
                if trimmed:
                    limitations.append(
                        f"Validation removed {llm_summary.claims_rejected} model claim(s) "
                        f"(sections: {', '.join(trimmed)}); see the rejected claims for the reasons."
                    )
                final_sections = [by_key[k] for k in ("summary", "market", "risk", "news", "documents")]
                if question:
                    final_sections.append(by_key["answer"])
                final_scenarios = [by_key[k] for k in ("bull", "base", "bear")]
                summary = llm_summary
                generation = GenerationInfo(
                    mode="llm",
                    provider=self._llm.name,
                    model=result.model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
                await step("synthesis", "ok", started, f"{llm_summary.claims_accepted} claims accepted, {llm_summary.claims_rejected} rejected")
            except Exception as exc:  # synthesis is optional: any failure degrades, never 500s
                if isinstance(exc, TimeoutError):
                    reason = "the language model timed out"
                else:
                    reason = getattr(exc, "message", None) or (
                        str(exc) if isinstance(exc, _InsufficientSynthesis) else "unexpected synthesis error"
                    )
                if not isinstance(exc, (ArgusError, _InsufficientSynthesis, TimeoutError)):
                    logger.exception("unexpected synthesis failure")
                logger.warning("llm synthesis fell back to deterministic", extra={"reason": reason})
                generation = GenerationInfo(mode="deterministic", provider=self._llm.name, model=self._llm.model, fallback_reason=reason)
                limitations.append(f"Language-model synthesis was unavailable ({reason}); showing the deterministic report.")
                await step("synthesis", "failed", started, reason)
        else:
            await step("synthesis", "skipped", started, "deterministic mode (no language model configured)")
        generation.validation = summary

        limitations.extend(_data_limitations(analysis, quote))
        report = ResearchReport(
            symbol=symbol,
            name=(profile.name if profile else quote.name if quote else None),
            question=question,
            generated_at=datetime.now(UTC).isoformat(),
            window={
                "label": analysis.window.label,
                "start": analysis.series.dates[0].isoformat(),
                "end": analysis.series.dates[-1].isoformat(),
                "benchmark": analysis.benchmark,
                "risk_free_rate": analysis.risk_free_rate,
                "observations": analysis.performance.observations,
            },
            sections=final_sections,
            scenarios=final_scenarios,
            evidence=ledger.items(),
            limitations=list(dict.fromkeys(limitations)),
            generation=generation,
            trace=trace,
        )
        if on_event:
            await on_event({"type": "step", "step": "report", "status": "ok", "detail": None})
        return report


class _InsufficientSynthesis(Exception):
    pass


# Question keywords -> metrics whose evidence directly answers them.
_QUESTION_METRICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("volatil", ("annualized_volatility",)),
    ("drawdown", ("max_drawdown", "current_drawdown")),
    ("beta", ("beta",)),
    ("sensitiv", ("beta",)),
    ("sharpe", ("sharpe_ratio",)),
    ("sortino", ("sortino_ratio",)),
    ("risk-adjusted", ("sharpe_ratio", "sortino_ratio")),
    ("tail", ("var_95", "cvar_95")),
    ("value at risk", ("var_95", "cvar_95")),
    ("var ", ("var_95", "cvar_95")),
    ("risk", ("annualized_volatility", "max_drawdown", "var_95", "beta")),
    ("return", ("total_return", "annualized_return")),
    ("perform", ("total_return", "annualized_return", "excess_annualized_return")),
    ("correlat", ("correlation",)),
    ("alpha", ("alpha",)),
    ("benchmark", ("excess_annualized_return", "beta")),
    ("market", ("beta", "excess_annualized_return")),
)
MAX_METRIC_ANSWERS = 5


def _metric_answer(question: str | None, ledger: EvidenceLedger) -> list[Claim]:
    """Deterministic answer to metric questions: restate the computed metrics
    the question asks about (verbatim evidence statements, so always valid)."""
    if not question:
        return []
    asked = f" {question.casefold()} "
    keys: list[str] = []
    for keyword, metric_keys in _QUESTION_METRICS:
        if keyword in asked:
            keys.extend(k for k in metric_keys if k not in keys)
    claims: list[Claim] = []
    for key in keys:
        evidence_id = ledger.metric_ids.get(key)
        item = ledger.get(evidence_id) if evidence_id else None
        if item is not None:
            claims.append(Claim(text=item.statement, kind=ClaimKind.FACT, evidence_ids=[item.id]))
    return claims[:MAX_METRIC_ANSWERS]


def _deterministic_summary(market: Section, risk_flags: list[Claim], conventions_id: str) -> Section:
    picks: list[Claim] = []
    for claim in market.claims:
        if claim.kind is ClaimKind.INTERPRETATION or "total return" in claim.text:
            picks.append(claim)
    cited = {claim.evidence_ids[0] for claim in picks if claim.evidence_ids}
    for flag in risk_flags:
        if flag.evidence_ids and flag.evidence_ids[0] not in cited:
            picks.append(flag)
            cited.add(flag.evidence_ids[0])
    if not risk_flags:
        picks.append(Claim(
            text="No ARGUS risk threshold (beta, volatility, drawdown, tail loss) was breached in this window.",
            kind=ClaimKind.INTERPRETATION,
            evidence_ids=[conventions_id],
        ))
    return Section(key="summary", title="Summary", claims=picks[:5])


def _data_limitations(analysis, quote) -> list[str]:
    notes: list[str] = []
    modes = {p.mode for p in analysis.provenance.values()}
    if DataMode.FIXTURE in modes:
        notes.append("This report uses ARGUS synthetic fixture data, not real market prices.")
    else:
        notes.append(
            "Prices come from Yahoo Finance via yfinance: free, unofficial, and possibly delayed; "
            "daily bars may include a still-forming latest session."
        )
    if any(p.stale for p in analysis.provenance.values()) or (quote and quote.provenance.stale):
        notes.append("Some inputs were served from a stale cache because the provider was unavailable.")
    notes.extend(analysis.warnings)
    notes.append(
        "Metrics are historical and computed by ARGUS's deterministic engine; they are not forecasts."
    )
    return notes
