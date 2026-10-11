'use client';

// Thin React wrapper around TradingView's lightweight-charts (Apache-2.0).
// Data always comes from the backend; nulls become gaps, never zeros.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';

export type ValueFormat = 'percent' | 'price' | 'ratio' | 'volume';

export interface SeriesSpec {
  id: string;
  label: string;
  type: 'line' | 'area' | 'histogram';
  color: string; // token name (e.g. "accent") or any CSS color
  dates: string[];
  values: (number | null)[];
  format?: ValueFormat;
  overlay?: boolean; // separate, compressed scale at the bottom (e.g. volume)
  lineWidth?: 1 | 2 | 3;
}

/** Horizontal guide drawn on the first series' scale (e.g. zero, beta = 1). */
export interface ReferenceLine {
  value: number;
  label: string;
  color?: string;
}

export function cssColor(token: string, alpha = 1): string {
  if (typeof window === 'undefined' || token.startsWith('#') || token.startsWith('rgb')) return token;
  const triplet = getComputedStyle(document.documentElement).getPropertyValue(`--${token}`).trim();
  return triplet ? `rgba(${triplet.split(/\s+/).join(', ')}, ${alpha})` : token;
}

export function formatValue(value: number | null | undefined, format: ValueFormat = 'price'): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  switch (format) {
    case 'percent':
      return `${(value * 100).toFixed(2)}%`;
    case 'ratio':
      return value.toFixed(2);
    case 'volume':
      return value >= 1e9 ? `${(value / 1e9).toFixed(2)}B` : value >= 1e6 ? `${(value / 1e6).toFixed(2)}M` : value >= 1e3 ? `${(value / 1e3).toFixed(1)}K` : value.toFixed(0);
    default:
      return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
}

interface LegendRow {
  id: string;
  label: string;
  color: string;
  value: number | null;
  format: ValueFormat;
}

export default function TimeSeriesChart({
  series,
  height = 280,
  ariaLabel,
  referenceLines = [],
}: {
  series: SeriesSpec[];
  height?: number;
  ariaLabel: string;
  referenceLines?: ReferenceLine[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [hoverDate, setHoverDate] = useState<string | null>(null);
  const [hoverValues, setHoverValues] = useState<Record<string, number | null>>({});

  const hasData = series.some((s) => s.values.some((v) => v !== null && Number.isFinite(v)));
  const signature = useMemo(
    () =>
      series.map((s) => `${s.id}:${s.dates.length}:${s.dates[0]}:${s.dates[s.dates.length - 1]}:${s.values[s.values.length - 1]}`).join('|') +
      referenceLines.map((r) => `@${r.value}:${r.label}`).join(''),
    [series, referenceLines],
  );

  useEffect(() => {
    if (!containerRef.current || !hasData) return;
    let disposed = false;
    let chart: IChartApi | null = null;
    let resizeObserver: ResizeObserver | null = null;

    void import('lightweight-charts').then(({ createChart, ColorType, CrosshairMode, LineStyle }) => {
      if (disposed || !containerRef.current) return;
      const line = cssColor('line');
      chart = createChart(containerRef.current, {
        autoSize: true,
        height,
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor: cssColor('ink-muted'),
          fontFamily: getComputedStyle(document.body).fontFamily,
          fontSize: 11,
        },
        grid: { vertLines: { color: cssColor('line', 0.45) }, horzLines: { color: cssColor('line', 0.45) } },
        rightPriceScale: { borderColor: line },
        timeScale: { borderColor: line, timeVisible: false },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: cssColor('ink-faint'), style: LineStyle.Dashed, labelBackgroundColor: cssColor('raised') },
          horzLine: { color: cssColor('ink-faint'), style: LineStyle.Dashed, labelBackgroundColor: cssColor('raised') },
        },
        handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
        handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true },
      });
      chartRef.current = chart;
      const apis = new Map<string, ISeriesApi<SeriesType>>();

      for (const spec of series) {
        const fmt = spec.format ?? 'price';
        const priceFormat = {
          type: 'custom' as const,
          formatter: (v: number) => formatValue(v, fmt),
          minMove: fmt === 'percent' ? 0.0001 : 0.01,
        };
        const common = {
          priceFormat,
          lastValueVisible: !spec.overlay,
          priceLineVisible: false,
          ...(spec.overlay ? { priceScaleId: `overlay-${spec.id}` } : {}),
        };
        let api: ISeriesApi<SeriesType>;
        if (spec.type === 'histogram') {
          api = chart.addHistogramSeries({ ...common, color: cssColor(spec.color, spec.overlay ? 0.35 : 0.8) });
        } else if (spec.type === 'area') {
          api = chart.addAreaSeries({
            ...common,
            lineColor: cssColor(spec.color),
            topColor: cssColor(spec.color, 0.28),
            bottomColor: cssColor(spec.color, 0.02),
            lineWidth: spec.lineWidth ?? 2,
          });
        } else {
          api = chart.addLineSeries({ ...common, color: cssColor(spec.color), lineWidth: spec.lineWidth ?? 2 });
        }
        if (spec.overlay) {
          chart.priceScale(`overlay-${spec.id}`).applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
        }
        api.setData(
          spec.dates.map((date, i) => {
            const value = spec.values[i];
            return value === null || value === undefined || !Number.isFinite(value)
              ? { time: date as Time }
              : { time: date as Time, value };
          }),
        );
        apis.set(spec.id, api);
      }
      const first = apis.values().next().value as ISeriesApi<SeriesType> | undefined;
      for (const ref of referenceLines) {
        first?.createPriceLine({
          price: ref.value,
          color: cssColor(ref.color ?? 'ink-faint', 0.8),
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: ref.label,
        });
      }
      // autoSize measures the container asynchronously; refit whenever the
      // width changes so the full date range always fills the plot.
      const fit = () => chart?.timeScale().fitContent();
      fit();
      requestAnimationFrame(fit);
      let lastWidth = 0;
      resizeObserver = new ResizeObserver((entries) => {
        const width = Math.round(entries[0]?.contentRect.width ?? 0);
        if (width && width !== lastWidth) {
          lastWidth = width;
          fit();
        }
      });
      resizeObserver.observe(containerRef.current);
      chart.subscribeCrosshairMove((param) => {
        if (!param.time) {
          setHoverDate(null);
          return;
        }
        const values: Record<string, number | null> = {};
        apis.forEach((api, id) => {
          const point = param.seriesData.get(api) as { value?: number } | undefined;
          values[id] = point?.value ?? null;
        });
        setHoverDate(String(param.time));
        setHoverValues(values);
      });
    });

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      chart?.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, height, hasData]);

  const legend: LegendRow[] = series.map((s) => {
    let last: number | null = null;
    for (let i = s.values.length - 1; i >= 0; i--) {
      const v = s.values[i];
      if (v !== null && Number.isFinite(v)) {
        last = v;
        break;
      }
    }
    return {
      id: s.id,
      label: s.label,
      color: s.color,
      value: hoverDate ? hoverValues[s.id] ?? null : last,
      format: s.format ?? 'price',
    };
  });

  if (!hasData) {
    return (
      <div className="flex items-center justify-center rounded border border-dashed border-line text-sm text-ink-muted" style={{ height }}>
        No data for this range.
      </div>
    );
  }

  return (
    <figure className="relative" aria-label={ariaLabel}>
      <figcaption className="mb-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-ink-muted">
        {legend.map((row) => (
          <span key={row.id} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm" style={{ background: cssColor(row.color) }} aria-hidden />
            {row.label}
            <span className="num text-ink">{formatValue(row.value, row.format)}</span>
          </span>
        ))}
        <span className="num ml-auto text-ink-faint">{hoverDate ?? ''}</span>
      </figcaption>
      <div ref={containerRef} style={{ height }} className="w-full" />
    </figure>
  );
}
