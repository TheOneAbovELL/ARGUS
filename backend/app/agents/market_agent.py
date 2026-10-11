"""Market Agent: price, trend, and benchmark context from verified inputs.

Purpose: describe where the asset trades and how it has performed.
Inputs: quote/profile evidence ids and the quant-engine metric ids.
Output: a ``market`` section of cited claims. It never computes metrics; it
only reads values already in the evidence ledger.
Failure mode: missing quote/profile evidence simply omits those claims.
"""

from app.agents.evidence import EvidenceLedger, pct
from app.agents.models import Claim, ClaimKind, Section
from app.services.analytics import AssetAnalysis


def trend_label(annualized_return: float) -> str:
    if annualized_return >= 0.20:
        return "strongly positive"
    if annualized_return >= 0:
        return "positive"
    if annualized_return > -0.20:
        return "negative"
    return "strongly negative"


def volatility_band(volatility: float) -> str:
    if volatility < 0.20:
        return "low"
    if volatility < 0.35:
        return "moderate"
    return "high"


class MarketAgent:
    key = "market"

    def analyze(
        self,
        analysis: AssetAnalysis,
        ledger: EvidenceLedger,
        quote_id: str | None,
        profile_ids: list[str],
        conventions_id: str,
    ) -> Section:
        claims: list[Claim] = []
        ids = ledger.metric_ids
        if quote_id:
            claims.append(Claim(text=ledger.get(quote_id).statement, kind=ClaimKind.FACT, evidence_ids=[quote_id]))
        if profile_ids:
            claims.append(
                Claim(text=ledger.get(profile_ids[0]).statement, kind=ClaimKind.FACT, evidence_ids=[profile_ids[0]])
            )
        perf, rel = analysis.performance, analysis.relative
        if "total_return" in ids:
            claims.append(Claim(text=ledger.get(ids["total_return"]).statement, kind=ClaimKind.FACT,
                                evidence_ids=[ids["total_return"]]))
        if perf.annualized_return is not None and "annualized_return" in ids:
            claims.append(
                Claim(
                    text=(
                        f"The annualized return of {pct(perf.annualized_return)} describes a "
                        f"{trend_label(perf.annualized_return)} historical trend over the window."
                    ),
                    kind=ClaimKind.INTERPRETATION,
                    evidence_ids=[ids["annualized_return"], conventions_id],
                )
            )
        if rel is not None and rel.excess_annualized_return is not None and "excess_annualized_return" in ids:
            direction = "outperformed" if rel.excess_annualized_return >= 0 else "underperformed"
            claims.append(
                Claim(
                    text=(
                        f"{analysis.symbol} {direction} {analysis.benchmark} by "
                        f"{pct(abs(rel.excess_annualized_return))} per year on an annualized basis."
                    ),
                    kind=ClaimKind.FACT,
                    evidence_ids=[ids["excess_annualized_return"]],
                )
            )
        if perf.annualized_volatility is not None and "annualized_volatility" in ids:
            claims.append(
                Claim(
                    text=(
                        f"Annualized volatility of {pct(perf.annualized_volatility)} is "
                        f"{volatility_band(perf.annualized_volatility)} relative to a broad-equity "
                        "reference range of roughly 15%-20%."
                    ),
                    kind=ClaimKind.INTERPRETATION,
                    evidence_ids=[ids["annualized_volatility"], conventions_id],
                )
            )
        return Section(key=self.key, title="Market & performance", claims=claims)
