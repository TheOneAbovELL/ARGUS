"""Document Agent: extractive evidence from the user's indexed documents.

Purpose: answer "what do the filings / transcripts say?" with verbatim,
page-cited passages. In deterministic mode it quotes rather than
paraphrases, so it cannot misstate a document.
"""

from app.agents.evidence import EvidenceLedger
from app.agents.models import Claim, ClaimKind, Section

QUOTE_CHARS = 320


def _quote(text: str) -> str:
    snippet = text if len(text) <= QUOTE_CHARS else text[:QUOTE_CHARS].rsplit(" ", 1)[0] + " …"
    return f"“{snippet}”"


class DocumentAgent:
    key = "documents"

    def analyze(self, ledger: EvidenceLedger, document_ids: list[str]) -> Section:
        claims = []
        for eid in document_ids:
            item = ledger.get(eid)
            claims.append(
                Claim(
                    text=f"{item.label}: {_quote(item.statement)}",
                    kind=ClaimKind.FACT,
                    evidence_ids=[eid],
                )
            )
        return Section(key=self.key, title="From your documents", claims=claims)
