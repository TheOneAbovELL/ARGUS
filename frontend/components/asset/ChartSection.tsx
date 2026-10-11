'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useAsync } from '@/lib/useAsync';
import { PERIODS, shortDate, type Period } from '@/lib/format';
import type { History, Technicals } from '@/lib/types';
import PriceWorkspace, { DEFAULT_SETTINGS, loadSettings, type WorkspaceSettings } from '@/components/charts/PriceWorkspace';
import DataBadge from '@/components/DataBadge';
import { ErrorNotice, LoadingBlock, Notes, SegmentedControl } from '@/components/ui';

const PERIOD_OPTIONS = PERIODS.map((p) => ({ value: p, label: p.toUpperCase() }));

/** The "Price history" section: period control + chart workspace. */
export default function ChartSection({
  symbol,
  period,
  onPeriod,
  data,
  error,
  loading,
  onRetry,
}: {
  symbol: string;
  period: Period;
  onPeriod: (p: Period) => void;
  data: Technicals | null;
  error: unknown;
  loading: boolean;
  onRetry: () => void;
}) {
  const [settings, setSettings] = useState<WorkspaceSettings>(DEFAULT_SETTINGS);
  useEffect(() => setSettings(loadSettings()), []);

  // The benchmark series is only fetched when the user turns "Compare" on.
  const benchmarkSymbol = data?.default_benchmark ?? null;
  const benchmark = useAsync<History | null>(
    () => (settings.compare && benchmarkSymbol && benchmarkSymbol !== symbol ? api.history(benchmarkSymbol, period) : Promise.resolve(null)),
    [settings.compare, benchmarkSymbol, period, symbol],
  );

  const periodControl = <SegmentedControl label="Chart period" size="xs" options={PERIOD_OPTIONS} value={period} onChange={onPeriod} />;

  return (
    <section aria-label="Price history" className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 pt-2.5">
        <h2 className="text-[13px] font-semibold text-ink">
          Price history <span className="font-normal text-ink-faint">· daily · {data?.currency ?? ''}</span>
        </h2>
        {data && <DataBadge provenance={data.provenance} />}
      </div>
      {error ? (
        <div className="p-3">
          <ErrorNotice error={error} onRetry={onRetry} />
        </div>
      ) : null}
      {loading && !data && !error && (
        <div className="p-4">
          <LoadingBlock rows={8} label="Loading chart" />
        </div>
      )}
      {data && (
        <div className={loading ? 'opacity-60 transition-opacity' : ''}>
          <PriceWorkspace
            data={data}
            benchmark={benchmark.data ?? null}
            settings={settings}
            onSettings={setSettings}
            periodControl={periodControl}
          />
          <div className="space-y-2 border-t border-line px-3 py-2">
            <p className="text-2xs text-ink-faint">
              {data.dates.length} daily bars, {shortDate(data.dates[0])} – {shortDate(data.dates[data.dates.length - 1])}. Candles use traded
              (split-adjusted) prices; return analytics use dividend-adjusted closes. Moving averages are warmed up with earlier history, so
              they are valid from the first visible bar. Drag to pan; drag an axis to zoom. Charts: TradingView Lightweight Charts.
            </p>
            {data.quality_notes.length > 0 && <Notes tone="info" items={data.quality_notes} />}
          </div>
        </div>
      )}
    </section>
  );
}
