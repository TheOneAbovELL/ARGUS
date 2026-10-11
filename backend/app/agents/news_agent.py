"""News Agent: attributable headlines from the market-data provider.

Purpose: list recent coverage with publisher and date so the user can read
the primary sources. It deliberately does *not* infer sentiment from
headlines — headline-level sentiment is unreliable and would be an
unsupported conclusion. Headlines are untrusted third-party text.
"""

from app.agents.evidence import EvidenceLedger
from app.agents.models import Claim, ClaimKind, Section

MAX_HEADLINES = 6


class NewsAgent:
    key = "news"

    def analyze(self, symbol: str, ledger: EvidenceLedger, news_ids: list[str]) -> Section:
        claims = [
            Claim(text=ledger.get(eid).statement, kind=ClaimKind.FACT, evidence_ids=[eid])
            for eid in news_ids[:MAX_HEADLINES]
        ]
        return Section(key=self.key, title="Recent news", claims=claims)
