'use client';

import { ExternalLink, Newspaper } from 'lucide-react';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/useAsync';
import { dateTime } from '@/lib/format';
import type { NewsFeed } from '@/lib/types';
import DataBadge from '@/components/DataBadge';
import { EmptyState, ErrorNotice, LoadingBlock, Panel } from '@/components/ui';

export default function NewsPanel({ symbol, limit = 12 }: { symbol: string; limit?: number }) {
  const { data, error, loading, reload } = useAsync<NewsFeed>(() => api.news(symbol, limit), [symbol, limit]);
  return (
    <Panel title="Recent headlines" actions={data && <DataBadge provenance={data.provenance} showProvider />} bodyClassName="p-0">
      {loading && !data && <div className="p-4"><LoadingBlock rows={5} /></div>}
      {error ? <div className="p-4"><ErrorNotice error={error} onRetry={reload} /></div> : null}
      {data && data.items.length === 0 && (
        <EmptyState icon={<Newspaper className="h-6 w-6" />} title="No headlines returned">
          The free news source returned nothing for {symbol}. This is a provider limitation, not evidence that nothing happened.
        </EmptyState>
      )}
      {data && data.items.length > 0 && (
        <ul className="divide-y divide-line">
          {data.items.map((item) => {
            const related = item.related_symbols.length > 0 && !item.related_symbols.includes(symbol);
            return (
              <li key={item.id} className="px-4 py-3">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noopener noreferrer" className="group text-sm font-medium text-ink hover:text-accent">
                        {item.title}
                        <ExternalLink className="ml-1 inline h-3 w-3 text-ink-faint group-hover:text-accent" aria-hidden />
                      </a>
                    ) : (
                      <p className="text-sm font-medium text-ink">{item.title}</p>
                    )}
                    <p className="mt-0.5 text-2xs text-ink-faint">
                      {item.publisher} · {item.published_at ? dateTime(item.published_at) : 'date unknown'}
                      {item.related_symbols.length > 0 && ` · tagged ${item.related_symbols.slice(0, 5).join(', ')}`}
                    </p>
                  </div>
                  {related && <span className="chip border-line text-ink-faint">related</span>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {data && data.items.length > 0 && (
        <p className="border-t border-line px-4 py-2 text-2xs text-ink-faint">
          Headlines are third-party content shown verbatim. ARGUS does not infer sentiment or price impact from them.
        </p>
      )}
    </Panel>
  );
}
