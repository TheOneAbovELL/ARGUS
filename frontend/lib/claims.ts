// How a research claim may be labelled, given what it cites.

import type { Claim, EvidenceItem } from './types';

/** What a claim's badge may honestly say, given what it cites. */
export function claimBadge(claim: Claim, evidence: Map<string, EvidenceItem>): { label: string; title: string } {
  if (claim.kind === 'interpretation') {
    return { label: 'Analysis', title: 'Analysis built on the cited evidence — not a sourced fact' };
  }
  const cited = claim.evidence_ids.map((id) => evidence.get(id)).filter((e): e is EvidenceItem => Boolean(e));
  if (cited.length > 0 && cited.every((e) => e.untrusted)) {
    return {
      label: 'Reported',
      title: 'Attributed to a third-party source (headline or your document); ARGUS has not verified its content',
    };
  }
  return { label: 'Fact', title: 'Directly supported by the cited evidence' };
}
