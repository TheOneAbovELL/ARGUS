'use client';

// TradingView-style price workspace on lightweight-charts (Apache-2.0):
// candles / line / area, overlays (SMA, EMA, Bollinger), volume, and
// synchronised RSI / MACD panes. Every value comes from the backend
// (/api/market/{symbol}/technicals); nothing is computed here.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { IChartApi, ISeriesApi, LogicalRange, SeriesType, Time } from 'lightweight-charts';
import { ChevronDown } from 'lucide-react';
import type { History, IndicatorKey, Technicals } from '@/lib/types';
import { cssColor, formatValue } from './TimeSeriesChart';

export type ChartStyle = 'candles' | 'line' | 'area';
export type Overlay = 'sma20' | 'sma50' | 'sma200' | 'ema20' | 'bollinger';
export type Pane = 'rsi' | 'macd';

export interface WorkspaceSettings {
  style: ChartStyle;
  overlays: Overlay[];
  panes: Pane[];
  volume: boolean;
  log: boolean;
  compare: boolean;
}

export const DEFAULT_SETTINGS: WorkspaceSettings = {
  style: 'candles',
  overlays: ['sma50', 'sma200'],
  panes: ['rsi'],
  volume: true,
  log: false,
  compare: false,
};

const OVERLAYS: { key: Overlay; label: string; color: string; hint: string }[] = [
  { key: 'sma20', label: 'SMA 20', color: 'chart-4', hint: 'Average of the last 20 closes — roughly one month' },
  { key: 'sma50', label: 'SMA 50', color: 'chart-1', hint: 'Average of the last 50 closes — the medium-term trend' },
  { key: 'sma200', label: 'SMA 200', color: 'chart-3', hint: 'Average of the last 200 closes — the long-term trend' },
  { key: 'ema20', label: 'EMA 20', color: 'chart-2', hint: 'Exponential average weighting recent closes more' },
  { key: 'bollinger', label: 'Bollinger (20, 2)', color: 'info', hint: '20-day average ± 2 standard deviations' },
];

const SETTINGS_KEY = 'argus.chart.settings.v1';

export function loadSettings(): WorkspaceSettings {
  try {
    const raw = window.localStorage.getItem(SETTINGS_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw), compare: false };
  } catch {
    /* storage unavailable: defaults */
  }
  return DEFAULT_SETTINGS;
}

function saveSettings(s: WorkspaceSettings) {
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);

function lineData(dates: string[], values: (number | null)[]) {
  return dates.map((d, i) => (isNum(values[i]) ? { time: d as Time, value: values[i] as number } : { time: d as Time }));
}

function baseOptions(height: number, showTime: boolean) {
  return {
    height,
    autoSize: true,
    layout: { textColor: cssColor('ink-muted'), fontSize: 11, fontFamily: getComputedStyle(document.body).fontFamily },
    grid: { vertLines: { color: cssColor('line', 0.35) }, horzLines: { color: cssColor('line', 0.35) } },
    rightPriceScale: { borderColor: cssColor('line'), minimumWidth: 76 },
    timeScale: { borderColor: cssColor('line'), visible: showTime, rightOffset: 4, minBarSpacing: 0.5 },
    // The wheel scrolls the page (this chart lives in a scrolling page);
    // drag pans, dragging an axis or pinching zooms.
    handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true },
  };
}

interface Hover {
  index: number;
}

export default function PriceWorkspace({
  data,
  benchmark,
  settings,
  onSettings,
  periodControl,
}: {
  data: Technicals;
  benchmark: History | null;
  settings: WorkspaceSettings;
  onSettings: (s: WorkspaceSettings) => void;
  periodControl: React.ReactNode;
}) {
  const mainRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const hasOhlc = useMemo(
    () => data.open.some(isNum) && data.high.some(isNum) && data.low.some(isNum),
    [data],
  );
  const hasVolume = data.volume.some((v) => isNum(v) && v > 0);
  const style: ChartStyle = settings.compare ? 'line' : !hasOhlc && settings.style === 'candles' ? 'line' : settings.style;
  const indexOf = useMemo(() => new Map(data.dates.map((d, i) => [d, i])), [data]);

  const update = (patch: Partial<WorkspaceSettings>) => {
    const next = { ...settings, ...patch };
    saveSettings(next);
    onSettings(next);
  };
  const toggle = <T extends string>(list: T[], item: T) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [menuOpen]);

  const signature = `${data.symbol}:${data.dates.length}:${data.dates[0]}:${data.as_of}:${JSON.stringify(settings)}:${benchmark?.dates.length ?? 0}`;

  useEffect(() => {
    if (!mainRef.current) return;
    let disposed = false;
    const charts: IChartApi[] = [];
    const observers: ResizeObserver[] = [];

    void import('lightweight-charts').then(({ createChart, CrosshairMode, LineStyle, PriceScaleMode }) => {
      if (disposed || !mainRef.current) return;
      const panes = settings.panes.filter((p) => (p === 'rsi' ? rsiRef.current : macdRef.current));
      const crosshair = {
        mode: CrosshairMode.Normal,
        vertLine: { color: cssColor('ink-faint'), style: LineStyle.Dashed, labelBackgroundColor: cssColor('raised') },
        horzLine: { color: cssColor('ink-faint'), style: LineStyle.Dashed, labelBackgroundColor: cssColor('raised') },
      };

      // ── main chart ─────────────────────────────────────────────────
      const main = createChart(mainRef.current, {
        ...baseOptions(mainRef.current.clientHeight || 440, panes.length === 0),
        crosshair,
        layout: { ...baseOptions(0, true).layout, background: { type: 'solid' as never, color: 'transparent' } },
        watermark: {
          visible: true,
          text: `${data.symbol} · 1D`,
          color: cssColor('ink', 0.05),
          fontSize: 44,
          horzAlign: 'center',
          vertAlign: 'center',
        },
      } as never);
      main.priceScale('right').applyOptions({
        mode: settings.compare ? PriceScaleMode.Percentage : settings.log ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
        scaleMargins: { top: 0.08, bottom: settings.volume && hasVolume ? 0.24 : 0.06 },
      });
      charts.push(main);

      let priceSeries: ISeriesApi<SeriesType>;
      if (style === 'candles') {
        priceSeries = main.addCandlestickSeries({
          upColor: cssColor('up'),
          downColor: cssColor('down'),
          wickUpColor: cssColor('up'),
          wickDownColor: cssColor('down'),
          borderVisible: false,
          priceLineColor: cssColor('ink-faint'),
        });
        priceSeries.setData(
          data.dates.map((d, i) => {
            const [o, h, l, c] = [data.open[i], data.high[i], data.low[i], data.close[i]];
            return isNum(o) && isNum(h) && isNum(l) && isNum(c) ? { time: d as Time, open: o, high: h, low: l, close: c } : { time: d as Time };
          }),
        );
      } else if (style === 'area') {
        priceSeries = main.addAreaSeries({
          lineColor: cssColor('accent'),
          topColor: cssColor('accent', 0.25),
          bottomColor: cssColor('accent', 0.0),
          lineWidth: 2,
        });
        priceSeries.setData(lineData(data.dates, data.close));
      } else {
        priceSeries = main.addLineSeries({ color: cssColor('accent'), lineWidth: 2 });
        priceSeries.setData(lineData(data.dates, data.close));
      }

      if (settings.compare && benchmark) {
        const bench = main.addLineSeries({ color: cssColor('chart-1'), lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: benchmark.symbol });
        // Align the benchmark to the asset's dates so both start together.
        const byDate = new Map(benchmark.dates.map((d, i) => [d, benchmark.close[i]]));
        bench.setData(data.dates.map((d) => (isNum(byDate.get(d)) ? { time: d as Time, value: byDate.get(d) as number } : { time: d as Time })));
      }

      if (!settings.compare) {
        for (const overlay of settings.overlays) {
          if (overlay === 'bollinger') {
            for (const [key, dashed] of [['bb_upper', false], ['bb_middle', true], ['bb_lower', false]] as const) {
              const s = main.addLineSeries({
                color: cssColor('info', dashed ? 0.6 : 0.8),
                lineWidth: 1,
                lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
              });
              s.setData(lineData(data.dates, data.indicators[key]));
            }
          } else {
            const meta = OVERLAYS.find((o) => o.key === overlay)!;
            const s = main.addLineSeries({
              color: cssColor(meta.color),
              lineWidth: 1,
              priceLineVisible: false,
              lastValueVisible: false,
              crosshairMarkerVisible: false,
            });
            s.setData(lineData(data.dates, data.indicators[overlay as IndicatorKey]));
          }
        }
      }

      if (settings.volume && hasVolume) {
        const vol = main.addHistogramSeries({ priceScaleId: 'volume', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false });
        main.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        vol.setData(
          data.dates.map((d, i) => {
            const v = data.volume[i];
            const up = i === 0 || data.close[i] >= data.close[i - 1];
            return isNum(v) ? { time: d as Time, value: v, color: cssColor(up ? 'up' : 'down', 0.35) } : { time: d as Time };
          }),
        );
      }

      // ── indicator panes ────────────────────────────────────────────
      const paneSeries: { chart: IChartApi; series: ISeriesApi<SeriesType>; values: (number | null)[] }[] = [];
      panes.forEach((pane, n) => {
        const el = pane === 'rsi' ? rsiRef.current! : macdRef.current!;
        const last = n === panes.length - 1;
        const chart = createChart(el, {
          ...baseOptions(el.clientHeight || 120, last),
          crosshair,
          // Attribution is shown once, on the main chart.
          layout: { ...baseOptions(0, true).layout, background: { type: 'solid' as never, color: 'transparent' }, attributionLogo: false },
        } as never);
        charts.push(chart);
        if (pane === 'rsi') {
          const s = chart.addLineSeries({ color: cssColor('chart-3'), lineWidth: 1, priceLineVisible: false });
          s.setData(lineData(data.dates, data.indicators.rsi14));
          s.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
          for (const level of [70, 30]) {
            s.createPriceLine({ price: level, color: cssColor('ink-faint'), lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: '' });
          }
          paneSeries.push({ chart, series: s, values: data.indicators.rsi14 });
        } else {
          const hist = chart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
          hist.setData(
            data.dates.map((d, i) => {
              const v = data.indicators.macd_hist[i];
              return isNum(v) ? { time: d as Time, value: v, color: cssColor(v >= 0 ? 'up' : 'down', 0.5) } : { time: d as Time };
            }),
          );
          const line = chart.addLineSeries({ color: cssColor('chart-2'), lineWidth: 1, priceLineVisible: false });
          line.setData(lineData(data.dates, data.indicators.macd));
          const sig = chart.addLineSeries({ color: cssColor('chart-1'), lineWidth: 1, priceLineVisible: false });
          sig.setData(lineData(data.dates, data.indicators.macd_signal));
          paneSeries.push({ chart, series: line, values: data.indicators.macd });
        }
      });

      // ── synchronisation: shared visible range and crosshair ────────
      let syncing = false;
      charts.forEach((source) => {
        source.timeScale().subscribeVisibleLogicalRangeChange((range: LogicalRange | null) => {
          if (syncing || !range) return;
          syncing = true;
          charts.forEach((target) => target !== source && target.timeScale().setVisibleLogicalRange(range));
          syncing = false;
        });
        source.subscribeCrosshairMove((param) => {
          const time = param.time ? String(param.time) : null;
          const index = time !== null ? indexOf.get(time) : undefined;
          setHover(index === undefined ? null : { index });
          const targets: { chart: IChartApi; series: ISeriesApi<SeriesType>; values: (number | null)[] }[] = [
            { chart: main, series: priceSeries, values: data.close },
            ...paneSeries,
          ];
          for (const t of targets) {
            if (t.chart === source) continue;
            const v = index === undefined ? null : t.values[index];
            if (time && isNum(v)) t.chart.setCrosshairPosition(v, time as Time, t.series);
            else t.chart.clearCrosshairPosition();
          }
        });
      });

      // autoSize measures asynchronously; refit when width changes so the
      // whole range fills the plot (fixes partial-width rendering).
      const fit = () => charts.forEach((c) => c.timeScale().fitContent());
      fit();
      requestAnimationFrame(fit);
      let lastWidth = 0;
      const ro = new ResizeObserver((entries) => {
        const width = Math.round(entries[0]?.contentRect.width ?? 0);
        if (width && width !== lastWidth) {
          lastWidth = width;
          fit();
        }
      });
      ro.observe(mainRef.current);
      observers.push(ro);
    });

    return () => {
      disposed = true;
      observers.forEach((o) => o.disconnect());
      charts.forEach((c) => c.remove());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  // ── legend (hovered bar, else latest) ────────────────────────────────
  const i = hover?.index ?? data.dates.length - 1;
  const prevClose = i > 0 ? data.close[i - 1] : null;
  const change = isNum(prevClose) ? data.close[i] / prevClose - 1 : null;
  const fmt = (v: number | null | undefined) => formatValue(v ?? null, 'price');
  const changeClass = change === null ? 'text-ink-muted' : change >= 0 ? 'text-up' : 'text-down';

  return (
    <div className="flex flex-col">
      {/* toolbar */}
      <div className="flex flex-wrap items-center gap-x-1 gap-y-1 border-b border-line px-2 py-1.5">
        {periodControl}
        <span className="mx-1 h-4 w-px bg-line" aria-hidden />
        <div role="radiogroup" aria-label="Chart type" className="flex items-center gap-0.5">
          {(['candles', 'line', 'area'] as const).map((s) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={style === s}
              disabled={settings.compare || (s === 'candles' && !hasOhlc)}
              title={s === 'candles' && !hasOhlc ? 'No open/high/low data for this symbol' : undefined}
              onClick={() => update({ style: s })}
              className="btn-tool disabled:opacity-40"
            >
              {s === 'candles' ? 'Candles' : s === 'line' ? 'Line' : 'Area'}
            </button>
          ))}
        </div>
        <span className="mx-1 h-4 w-px bg-line" aria-hidden />
        <div className="relative" ref={menuRef}>
          <button type="button" className="btn-tool" aria-expanded={menuOpen} aria-haspopup="true" onClick={() => setMenuOpen((o) => !o)}>
            Indicators <span className="num text-ink-faint">{settings.overlays.length + settings.panes.length}</span>
            <ChevronDown className="h-3 w-3" aria-hidden />
          </button>
          {menuOpen && (
            <div className="absolute left-0 top-full z-30 mt-1 w-72 rounded border border-line bg-raised p-1 shadow-xl shadow-black/50">
              <p className="px-2 pb-1 pt-1.5 text-2xs font-medium text-ink-faint">Overlays on price</p>
              {OVERLAYS.map((o) => (
                <label key={o.key} className="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 hover:bg-bg">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-[rgb(var(--accent))]"
                    checked={settings.overlays.includes(o.key)}
                    onChange={() => update({ overlays: toggle(settings.overlays, o.key) })}
                  />
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5 text-[13px] text-ink">
                      <span className="h-0.5 w-3 rounded" style={{ background: cssColor(o.color) }} aria-hidden />
                      {o.label}
                    </span>
                    <span className="block text-2xs text-ink-faint">{o.hint}</span>
                  </span>
                </label>
              ))}
              <p className="px-2 pb-1 pt-2 text-2xs font-medium text-ink-faint">Panes below</p>
              {([
                ['rsi', 'RSI (14)', 'Momentum oscillator, 0–100; 70 / 30 marked'],
                ['macd', 'MACD (12, 26, 9)', 'Trend momentum: MACD, signal and histogram'],
              ] as const).map(([key, label, hint]) => (
                <label key={key} className="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 hover:bg-bg">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={settings.panes.includes(key)}
                    onChange={() => update({ panes: toggle(settings.panes, key) })}
                  />
                  <span>
                    <span className="block text-[13px] text-ink">{label}</span>
                    <span className="block text-2xs text-ink-faint">{hint}</span>
                  </span>
                </label>
              ))}
              {hasVolume && (
                <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 hover:bg-bg">
                  <input type="checkbox" checked={settings.volume} onChange={() => update({ volume: !settings.volume })} />
                  <span className="text-[13px] text-ink">Volume</span>
                </label>
              )}
            </div>
          )}
        </div>
        <button
          type="button"
          className="btn-tool"
          aria-pressed={settings.compare}
          disabled={!benchmark}
          onClick={() => update({ compare: !settings.compare })}
          title={`Compare % change with ${data.default_benchmark}`}
        >
          Compare {data.default_benchmark}
        </button>
        <button type="button" className="btn-tool" aria-pressed={settings.log} disabled={settings.compare} onClick={() => update({ log: !settings.log })} title="Logarithmic price scale">
          Log
        </button>
      </div>

      {/* legend */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-3 pt-2 text-xs">
        <span className="num text-ink-faint">{data.dates[i]}</span>
        {!settings.compare && hasOhlc && (
          <>
            <span className="text-ink-faint">O <span className={`num ${changeClass}`}>{fmt(data.open[i])}</span></span>
            <span className="text-ink-faint">H <span className={`num ${changeClass}`}>{fmt(data.high[i])}</span></span>
            <span className="text-ink-faint">L <span className={`num ${changeClass}`}>{fmt(data.low[i])}</span></span>
          </>
        )}
        <span className="text-ink-faint">C <span className={`num ${changeClass}`}>{fmt(data.close[i])}</span></span>
        <span className={`num ${changeClass}`}>{change === null ? '' : `${change >= 0 ? '+' : ''}${(change * 100).toFixed(2)}%`}</span>
        {hasVolume && <span className="text-ink-faint">Vol <span className="num text-ink">{formatValue(data.volume[i], 'volume')}</span></span>}
        {!settings.compare &&
          settings.overlays
            .filter((o) => o !== 'bollinger')
            .map((o) => {
              const meta = OVERLAYS.find((x) => x.key === o)!;
              return (
                <span key={o} style={{ color: cssColor(meta.color) }}>
                  {meta.label} <span className="num">{fmt(data.indicators[o as IndicatorKey][i])}</span>
                </span>
              );
            })}
        {!settings.compare && settings.overlays.includes('bollinger') && (
          <span style={{ color: cssColor('info') }}>
            BB <span className="num">{fmt(data.indicators.bb_upper[i])} / {fmt(data.indicators.bb_lower[i])}</span>
          </span>
        )}
        {settings.compare && benchmark && <span style={{ color: cssColor('chart-1') }}>vs {benchmark.symbol} (% change from the first visible bar)</span>}
      </div>

      <figure aria-label={`${data.symbol} daily closing price`} className="m-0">
        <div ref={mainRef} className="h-[360px] w-full sm:h-[440px]" />
      </figure>
      {settings.panes.includes('rsi') && (
        <div className="border-t border-line">
          <p className="px-3 pt-1 text-2xs text-ink-faint">
            RSI 14 <span className="num" style={{ color: cssColor('chart-3') }}>{formatValue(data.indicators.rsi14[i], 'ratio')}</span>
          </p>
          <div ref={rsiRef} className="h-[110px] w-full" aria-label="RSI pane" />
        </div>
      )}
      {settings.panes.includes('macd') && (
        <div className="border-t border-line">
          <p className="px-3 pt-1 text-2xs text-ink-faint">
            MACD 12 26 9 <span className="num" style={{ color: cssColor('chart-2') }}>{formatValue(data.indicators.macd[i], 'ratio')}</span>{' '}
            <span className="num" style={{ color: cssColor('chart-1') }}>{formatValue(data.indicators.macd_signal[i], 'ratio')}</span>{' '}
            <span className="num text-ink-muted">{formatValue(data.indicators.macd_hist[i], 'ratio')}</span>
          </p>
          <div ref={macdRef} className="h-[130px] w-full" aria-label="MACD pane" />
        </div>
      )}
    </div>
  );
}
