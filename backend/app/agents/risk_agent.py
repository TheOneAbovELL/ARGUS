"""Risk Agent: classify risk from verified quant-engine outputs.

Purpose: surface market sensitivity, tail risk, drawdown, and risk-adjusted
performance, with explicit thresholds.
Inputs: metric evidence ids only (no provider calls, no recomputation).
Output: a ``risk`` section and a list of risk-flag claims.
Thresholds are conventions, not universal truths, and are stated as such.
"""

from app.agents.evidence import EvidenceLedger, num, pct
from app.agents.models import Claim, ClaimKind, Section
from app.services.analytics import AssetAnalysis


class RiskAgent:
    key = "risk"

    def analyze(
        self, analysis: AssetAnalysis, ledger: EvidenceLedger, conventions_id: str
    ) -> tuple[Section, list[Claim]]:
        ids = ledger.metric_ids
        c = conventions_id
        perf, rel = analysis.performance, analysis.relative
        claims: list[Claim] = []
        flags: list[Claim] = []

        for key in ("max_drawdown", "var_95", "cvar_95", "sharpe_ratio"):
            if key in ids:
                claims.append(Claim(text=ledger.get(ids[key]).statement, kind=ClaimKind.FACT, evidence_ids=[ids[key]]))
        if rel is not None and rel.beta is not None and "beta" in ids:
            claims.append(Claim(text=ledger.get(ids["beta"]).statement, kind=ClaimKind.FACT, evidence_ids=[ids["beta"]]))
            if rel.beta > 1.2:
                flags.append(Claim(
                    text=f"Above-market sensitivity: beta of {num(rel.beta)} exceeds the 1.2 threshold ARGUS uses for elevated market exposure.",
                    kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["beta"], c]))
            elif rel.beta < 0:
                flags.append(Claim(
                    text=f"Historically inverse market exposure: beta of {num(rel.beta)} is negative.",
                    kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["beta"], c]))
        if perf.annualized_volatility is not None and perf.annualized_volatility >= 0.35 and "annualized_volatility" in ids:
            flags.append(Claim(
                text=f"High realized volatility: {pct(perf.annualized_volatility)} annualized, above the 35% threshold.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["annualized_volatility"], c]))
        if "max_drawdown" in ids and perf.max_drawdown <= -0.15:
            severity = "Severe" if perf.max_drawdown <= -0.30 else "Material"
            flags.append(Claim(
                text=f"{severity} historical drawdown: the asset fell {pct(abs(perf.max_drawdown))} from a prior peak within the window.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["max_drawdown"], c]))
        if perf.sharpe_ratio is not None and perf.sharpe_ratio < 0 and "sharpe_ratio" in ids:
            flags.append(Claim(
                text=f"Negative risk-adjusted return: Sharpe ratio of {num(perf.sharpe_ratio)}.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["sharpe_ratio"]]))
        if perf.var_95 is not None and perf.var_95 <= -0.03 and "var_95" in ids:
            flags.append(Claim(
                text=f"Fat daily tail: on 5% of days the return was {pct(perf.var_95)} or worse.",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["var_95"], c]))
        if perf.sharpe_ratio is not None and "sharpe_ratio" in ids:
            quality = "strong" if perf.sharpe_ratio >= 1 else "positive but modest" if perf.sharpe_ratio >= 0 else "negative"
            claims.append(Claim(
                text=f"Risk-adjusted performance was {quality} over the window (Sharpe {num(perf.sharpe_ratio)}).",
                kind=ClaimKind.INTERPRETATION, evidence_ids=[ids["sharpe_ratio"], c]))
        return Section(key=self.key, title="Risk profile", claims=claims + flags), flags
