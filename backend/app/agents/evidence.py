"""The evidence ledger: every number and passage a report may rely on.

Evidence is built deterministically from provider data, the quant engine,
news feeds, and retrieved document passages *before* any synthesis happens.
Each item has a stable short id (``Q1``, ``M4``, ``N2``, ``D3`` …) and a
canonical ``statement`` whose formatted numbers are what claims must match.
"""

import math
from collections import defaultdict
from datetime import date, datetime

from app.agents.models import EvidenceItem
from app.knowledge.vector_store import RetrievedChunk
from app.providers.models import AssetProfile, NewsItem, Provenance, Quote
from app.services.analytics import AssetAnalysis

_PREFIX = {"quote": "Q", "profile": "P", "metric": "M", "news": "N", "document": "D", "method": "C"}
MAX_DOCUMENT_EXCERPT = 900


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def num(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


def money(value: float, currency: str | None) -> str:
    return f"{value:,.2f} {currency}" if currency else f"{value:,.2f}"


def compact(value: float, small_decimals: int = 2) -> str:
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= threshold:
            return f"{value / threshold:.2f}{suffix}"
    return num(value, small_decimals)


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _source(provenance: Provenance) -> str:
    flags = []
    if provenance.mode.value == "fixture":
        flags.append("synthetic fixture data")
    if provenance.stale:
        flags.append("stale cached copy")
    return provenance.provider + (f" ({', '.join(flags)})" if flags else "")


class EvidenceLedger:
    def __init__(self) -> None:
        self._items: dict[str, EvidenceItem] = {}
        self._counters: dict[str, int] = defaultdict(int)
        self.metric_ids: dict[str, str] = {}

    def add(self, kind: str, **fields) -> str:
        self._counters[kind] += 1
        evidence_id = f"{_PREFIX[kind]}{self._counters[kind]}"
        self._items[evidence_id] = EvidenceItem(id=evidence_id, kind=kind, **fields)
        return evidence_id

    def get(self, evidence_id: str) -> EvidenceItem | None:
        return self._items.get(evidence_id)

    def __contains__(self, evidence_id: str) -> bool:
        return evidence_id in self._items

    def items(self, kind: str | None = None) -> list[EvidenceItem]:
        return [item for item in self._items.values() if kind is None or item.kind == kind]

    # ── builders ───────────────────────────────────────────────────────

    def add_conventions(self) -> str:
        """ARGUS's own classification thresholds, cited by interpretive
        claims so that their numbers are traceable too."""
        return self.add(
            "method",
            label="ARGUS classification conventions",
            statement=(
                "ARGUS classification conventions (heuristics, not universal standards): beta above "
                "1.20 = elevated market sensitivity; annualized volatility below 20.00% = low, "
                "20.00% to 35.00% = moderate, 35.00% or more = high (broad equity indices have "
                "typically run around 15%-20%); a maximum drawdown of 15.00% or more = material and "
                "30.00% or more = severe; a 1-day 95% historical VaR of -3.00% or worse = fat daily "
                "tail; an annualized return of 20.00% or more = strongly positive trend, -20.00% or "
                "worse = strongly negative; Sharpe ratio of 1.00 or more = strong."
            ),
            source="ARGUS methodology",
        )

    def add_quote(self, quote: Quote) -> str:
        change = quote.change_percent
        parts = [f"Last price {money(quote.price, quote.currency)}"]
        if quote.previous_close is not None:
            parts.append(f"previous close {money(quote.previous_close, quote.currency)}")
        if change is not None:
            parts.append(f"change {change * 100:+.2f}%")
        freshness = "delayed quote" if quote.provenance.mode.value == "delayed" else quote.provenance.mode.value
        return self.add(
            "quote",
            label=f"{quote.symbol} latest quote",
            statement="; ".join(parts) + f" ({freshness}).",
            source=_source(quote.provenance),
            as_of=_iso(quote.provenance.as_of),
            value=quote.price,
            unit="currency",
        )

    def add_profile(self, profile: AssetProfile) -> list[str]:
        ids: list[str] = []
        descriptor = ", ".join(
            part
            for part in (
                profile.quote_type,
                f"sector {profile.sector}" if profile.sector else None,
                f"industry {profile.industry}" if profile.industry else None,
                profile.country,
            )
            if part
        )
        if descriptor:
            ids.append(
                self.add(
                    "profile",
                    label=f"{profile.symbol} classification",
                    statement=f"{profile.name}: {descriptor}.",
                    source=_source(profile.provenance),
                    as_of=_iso(profile.provenance.retrieved_at),
                )
            )
        for stat in profile.stats:
            if stat.value is None:
                continue
            if stat.unit == "percent":
                rendered = pct(stat.value)
            elif stat.unit == "currency":
                rendered = f"{compact(stat.value)} {stat.currency or ''}".strip() + (
                    f" ({num(stat.value, 0)})" if abs(stat.value) >= 1e6 else ""
                )
            elif stat.unit == "count":
                rendered = f"{compact(stat.value, 0)} ({num(stat.value, 0)})"
            else:
                rendered = num(stat.value)
            ids.append(
                self.add(
                    "profile",
                    label=f"{stat.label}",
                    statement=f"{stat.label}: {rendered} (provider-reported).",
                    source=_source(profile.provenance),
                    as_of=_iso(profile.provenance.retrieved_at),
                    value=stat.value,
                    unit=stat.unit,
                )
            )
        return ids

    def add_analysis(self, analysis: AssetAnalysis) -> None:
        perf = analysis.performance
        rel = analysis.relative
        overlap = analysis.comparison.dates if analysis.comparison else analysis.series.dates
        window = f"{overlap[0].isoformat()} to {overlap[-1].isoformat()}"
        data_window = f"{analysis.series.dates[0].isoformat()} to {analysis.series.dates[-1].isoformat()}"
        source = "ARGUS quant engine on " + _source(analysis.provenance[analysis.symbol])
        as_of = analysis.series.dates[-1].isoformat()
        rf = pct(analysis.risk_free_rate)

        def metric(key: str, label: str, value: float | None, statement: str, unit: str) -> None:
            if value is None or not math.isfinite(value):
                return
            self.metric_ids[key] = self.add(
                "metric",
                label=label,
                statement=statement,
                source=source,
                as_of=as_of,
                value=value,
                unit=unit,
            )

        s = analysis.symbol
        metric("total_return", "Total return", perf.total_return,
               f"{s} total return (dividend-adjusted) over {data_window}: {pct(perf.total_return)}.", "percent")
        metric("annualized_return", "Annualized return (CAGR)", perf.annualized_return,
               f"{s} annualized return (CAGR) over {data_window}: "
               f"{pct(perf.annualized_return) if perf.annualized_return is not None else ''}.", "percent")
        metric("annualized_volatility", "Annualized volatility", perf.annualized_volatility,
               f"{s} annualized volatility of daily returns over {data_window}: "
               f"{pct(perf.annualized_volatility) if perf.annualized_volatility is not None else ''}.", "percent")
        metric("sharpe_ratio", "Sharpe ratio", perf.sharpe_ratio,
               f"{s} annualized Sharpe ratio (risk-free rate {rf}): "
               f"{num(perf.sharpe_ratio) if perf.sharpe_ratio is not None else ''}.", "ratio")
        metric("sortino_ratio", "Sortino ratio", perf.sortino_ratio,
               f"{s} annualized Sortino ratio (risk-free rate {rf}): "
               f"{num(perf.sortino_ratio) if perf.sortino_ratio is not None else ''}.", "ratio")
        recovery = (
            f"recovered on {perf.max_drawdown_recovery.isoformat()}"
            if perf.max_drawdown_recovery
            else "not recovered by the end of the window"
        )
        metric("max_drawdown", "Maximum drawdown", perf.max_drawdown,
               f"{s} maximum drawdown: {pct(perf.max_drawdown)} from the peak on "
               f"{perf.max_drawdown_peak.isoformat()} to the trough on {perf.max_drawdown_trough.isoformat()}; "
               f"{recovery}.", "percent")
        metric("current_drawdown", "Current drawdown", perf.current_drawdown,
               f"{s} drawdown from its running peak at the last observation ({as_of}): "
               f"{pct(perf.current_drawdown)}.", "percent")
        metric("var_95", "1-day historical VaR (95%)", perf.var_95,
               f"{s} 1-day historical VaR at 95%: {pct(perf.var_95) if perf.var_95 is not None else ''} "
               "(5th percentile of daily returns: the lowest 5% of days were at or below this level).", "percent")
        metric("cvar_95", "1-day historical CVaR (95%)", perf.cvar_95,
               f"{s} 1-day expected shortfall at 95%: {pct(perf.cvar_95) if perf.cvar_95 is not None else ''} "
               "(mean of returns at or below the VaR).", "percent")
        metric("worst_period", "Worst daily return", perf.worst_period,
               f"{s} worst daily return in the window: {pct(perf.worst_period)}.", "percent")
        metric("best_period", "Best daily return", perf.best_period,
               f"{s} best daily return in the window: {pct(perf.best_period)}.", "percent")
        if rel is not None:
            b = analysis.benchmark
            metric("beta", "Beta", rel.beta,
                   f"{s} beta versus {b} (daily excess returns, {window}): "
                   f"{num(rel.beta) if rel.beta is not None else ''}.", "ratio")
            metric("correlation", "Correlation", rel.correlation,
                   f"{s} correlation of daily returns with {b}: "
                   f"{num(rel.correlation) if rel.correlation is not None else ''}.", "ratio")
            metric("alpha", "Alpha (annualized)", rel.alpha,
                   f"{s} annualized Jensen's alpha versus {b}: {pct(rel.alpha) if rel.alpha is not None else ''}.",
                   "percent")
            metric("benchmark_total_return", "Benchmark total return", rel.benchmark_total_return,
                   f"{b} total return over the overlapping dates: {pct(rel.benchmark_total_return)}.", "percent")
            metric("excess_annualized_return", "Excess annualized return", rel.excess_annualized_return,
                   f"{s} annualized return minus {b} annualized return: "
                   f"{pct(rel.excess_annualized_return) if rel.excess_annualized_return is not None else ''}.",
                   "percent")
            metric("tracking_error", "Tracking error", rel.tracking_error,
                   f"{s} annualized tracking error versus {b}: "
                   f"{pct(rel.tracking_error) if rel.tracking_error is not None else ''}.", "percent")

    def add_news(self, item: NewsItem, symbol: str, provenance: Provenance) -> str:
        published = item.published_at.date().isoformat() if item.published_at else "date not provided"
        specific = symbol in item.related_symbols
        return self.add(
            "news",
            label=item.publisher,
            statement=(
                f'Headline: "{item.title}" — {item.publisher}, {published}'
                + ("" if specific else " (the provider did not tag this article to the symbol)")
                + "."
            ),
            source=_source(provenance),
            as_of=item.published_at.isoformat() if item.published_at else None,
            url=item.url,
            untrusted=True,
        )

    def add_document(self, chunk: RetrievedChunk) -> str:
        excerpt = chunk.text if len(chunk.text) <= MAX_DOCUMENT_EXCERPT else chunk.text[:MAX_DOCUMENT_EXCERPT] + " …"
        return self.add(
            "document",
            label=f"{chunk.title}, p. {chunk.page_number}",
            statement=excerpt,
            source=f"{chunk.title} ({chunk.document_type.value}; {chunk.source})",
            as_of=chunk.published_on.isoformat() if chunk.published_on else None,
            document_id=chunk.document_id or None,
            page_number=chunk.page_number,
            chunk_id=chunk.id,
            retrieval_score=round(chunk.score, 4),
            untrusted=True,
        )
