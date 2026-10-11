'use client';

import { useState } from 'react';
import { compact, count, num, pct, price } from '@/lib/format';
import type { KeyStat, Profile } from '@/lib/types';
import DataBadge from '@/components/DataBadge';
import { ErrorNotice, LoadingBlock, StatList } from '@/components/ui';

function statValue(stat: KeyStat, marketCurrency: string | null): string {
  switch (stat.unit) {
    case 'percent':
      return pct(stat.value);
    case 'currency':
      return Math.abs(stat.value ?? 0) >= 1e6 ? compact(stat.value, stat.currency) : price(stat.value, stat.currency);
    case 'count':
      return count(stat.value, marketCurrency);
    default:
      return num(stat.value);
  }
}

const GROUPS: { title: string; keys: string[] }[] = [
  { title: 'Valuation', keys: ['market_cap', 'trailing_pe', 'forward_pe', 'price_to_book', 'dividend_yield'] },
  { title: 'Fundamentals (TTM)', keys: ['revenue', 'revenue_growth', 'gross_margin', 'operating_margin', 'profit_margin', 'return_on_equity', 'free_cash_flow'] },
  { title: 'Trading', keys: ['high_52w', 'low_52w', 'avg_volume', 'shares_outstanding', 'provider_beta'] },
];

const toneFor = (stat: KeyStat) =>
  stat.unit === 'percent' && stat.key !== 'dividend_yield' && typeof stat.value === 'number'
    ? stat.value >= 0
      ? 'text-up'
      : 'text-down'
    : undefined;

export default function ProfilePanel({
  profile,
  error,
  loading,
  onRetry,
}: {
  profile: Profile | null;
  error: unknown;
  loading: boolean;
  onRetry: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const byKey = new Map(profile?.stats.map((s) => [s.key, s]) ?? []);
  return (
    <section aria-label="Profile and key statistics" className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[13px] font-semibold text-ink">Key statistics</h2>
        {profile && <DataBadge provenance={profile.provenance} />}
      </div>
      {loading && !profile && <LoadingBlock rows={6} />}
      {error ? <ErrorNotice error={error} onRetry={onRetry} compact /> : null}
      {profile && (
        <>
          {GROUPS.map((group) => {
            const rows = group.keys.map((k) => byKey.get(k)).filter((s): s is KeyStat => !!s);
            if (!rows.length) return null;
            return (
              <div key={group.title}>
                <h3 className="mb-1 text-xs font-medium text-ink-faint">{group.title}</h3>
                <StatList rows={rows.map((s) => ({ label: s.label, value: statValue(s, profile.currency), tone: toneFor(s) }))} />
              </div>
            );
          })}
          <p className="text-2xs text-ink-faint">Reported by {profile.provenance.provider}; not recomputed by ARGUS and may lag company filings.</p>
          <div>
            <h3 className="mb-1 text-xs font-medium text-ink-faint">About</h3>
            <StatList
              rows={[
                ['Sector', profile.sector],
                ['Industry', profile.industry],
                ['Country', profile.country],
                ['Currency', profile.currency],
              ]
                .filter(([, v]) => v)
                .map(([k, v]) => ({ label: k as string, value: <span className="font-normal">{v}</span> }))}
            />
            {profile.summary && (
              <div className="mt-2">
                <p className={`text-[13px] leading-relaxed text-ink-muted ${expanded ? '' : 'line-clamp-5'}`}>{profile.summary}</p>
                {profile.summary.length > 300 && (
                  <button type="button" className="mt-1 text-xs text-accent hover:underline" onClick={() => setExpanded((e) => !e)}>
                    {expanded ? 'Show less' : 'Read more'}
                  </button>
                )}
              </div>
            )}
            {profile.website && /^https?:\/\//.test(profile.website) && (
              <a href={profile.website} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-xs text-accent hover:underline">
                {profile.website.replace(/^https?:\/\//, '')}
              </a>
            )}
          </div>
        </>
      )}
    </section>
  );
}
