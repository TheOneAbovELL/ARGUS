import { describe, expect, it } from 'vitest';
import { claimBadge } from '@/lib/claims';
import type { Claim, EvidenceItem } from '@/lib/types';

const item = (id: string, kind: EvidenceItem['kind'], untrusted: boolean): EvidenceItem => ({
  id,
  kind,
  label: id,
  statement: '',
  source: 'test',
  as_of: null,
  value: null,
  unit: null,
  url: null,
  document_id: null,
  page_number: null,
  chunk_id: null,
  retrieval_score: null,
  untrusted,
});

const evidence = new Map([
  ['M1', item('M1', 'metric', false)],
  ['D1', item('D1', 'document', true)],
  ['N1', item('N1', 'news', true)],
]);

const claim = (kind: Claim['kind'], ids: string[]): Claim => ({ text: 'x', kind, evidence_ids: ids });

describe('claimBadge', () => {
  it('labels interpretations as analysis', () => {
    expect(claimBadge(claim('interpretation', ['M1']), evidence).label).toBe('Analysis');
  });

  it('labels facts backed by ARGUS evidence as facts', () => {
    expect(claimBadge(claim('fact', ['M1']), evidence).label).toBe('Fact');
    expect(claimBadge(claim('fact', ['M1', 'D1']), evidence).label).toBe('Fact');
  });

  it('never presents third-party-only claims as verified facts', () => {
    expect(claimBadge(claim('fact', ['D1']), evidence).label).toBe('Reported');
    expect(claimBadge(claim('fact', ['N1', 'D1']), evidence).label).toBe('Reported');
  });
});
