"""Strategy Agent: balanced scenarios built only from other agents' evidence.

Purpose: frame bull / base / bear hypotheses for further research. Every
scenario statement is an *interpretation* that cites the evidence it rests
on. It does not issue buy/sell instructions, price targets, or position
sizes — ARGUS has no basis for those.
"""

from app.agents.evidence import EvidenceLedger, num, pct
from app.agents.models import Claim, ClaimKind, Section
from app.services.analytics import AssetAnalysis


class StrategyAgent:
    key = "scenarios"

    def analyze(
        self,
        analysis: AssetAnalysis,
        ledger: EvidenceLedger,
        risk_flags: list[Claim],
        news_ids: list[str],
        document_ids: list[str],
    ) -> list[Section]:
        ids = ledger.metric_ids
        perf, rel = analysis.performance, analysis.relative
        s = analysis.symbol

        bull: list[Claim] = []
        if perf.annualized_return is not None and perf.annualized_return > 0 and "annualized_return" in ids:
            bull.append(Claim(
                text=f"Momentum case: {s} compounded at {pct(perf.annualized_return)} per year in the window; a continuation would extend that trend.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["annualized_return"]]))
        if rel is not None and rel.alpha is not None and rel.alpha > 0 and "alpha" in ids:
            bull.append(Claim(
                text=f"Returns were not explained by market exposure alone: annualized alpha of {pct(rel.alpha)} versus {analysis.benchmark}.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["alpha"]]))
        if perf.sharpe_ratio is not None and perf.sharpe_ratio >= 1 and "sharpe_ratio" in ids:
            bull.append(Claim(
                text=f"Risk-adjusted returns were strong (Sharpe {num(perf.sharpe_ratio)}).",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["sharpe_ratio"]]))
        if document_ids:
            bull.append(Claim(
                text="Review the cited document passages for company-stated drivers that could support continued performance.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=document_ids[:2]))

        bear: list[Claim] = [flag.model_copy() for flag in risk_flags]
        if perf.annualized_return is not None and perf.annualized_return < 0 and "annualized_return" in ids:
            bear.append(Claim(
                text=f"Trend case: {s} lost {pct(abs(perf.annualized_return))} per year in the window; a continuation would extend losses.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["annualized_return"]]))
        if perf.current_drawdown < -0.10 and "current_drawdown" in ids:
            bear.append(Claim(
                text=f"{s} remains {pct(abs(perf.current_drawdown))} below its running peak at the last observation.",
                kind=ClaimKind.FACT, evidence_ids=[ids["current_drawdown"]]))

        base: list[Claim] = [Claim(
            text="Base case: historical return and risk statistics describe the past window only; they are not forecasts, and regime changes can invalidate them.",
            kind=ClaimKind.INTERPRETATION,
            evidence_ids=[ids[k] for k in ("annualized_return", "annualized_volatility") if k in ids])]
        if news_ids:
            base.append(Claim(
                text="Recent headlines are listed for follow-up; ARGUS does not score their sentiment or price impact.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=news_ids[:2]))
        if rel is not None and rel.r_squared is not None and "correlation" in ids:
            base.append(Claim(
                text=f"Co-movement with {analysis.benchmark}: correlation of {num(rel.correlation)}, so broad-market moves are "
                     + ("a major" if rel.r_squared >= 0.5 else "only a partial") + " driver of this asset's returns.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["correlation"]]))

        return [
            Section(key="bull", title="Bull case", claims=bull),
            Section(key="base", title="Base case", claims=base),
            Section(key="bear", title="Bear case", claims=bear),
        ]
