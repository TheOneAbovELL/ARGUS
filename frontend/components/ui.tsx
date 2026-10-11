'use client';

import Link from 'next/link';
import { AlertTriangle, Info, Loader2, RefreshCw } from 'lucide-react';
import { ApiError, describeError } from '@/lib/api';

export function Panel({
  title,
  actions,
  children,
  className = '',
  bodyClassName = 'p-4',
}: {
  title?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`panel animate-fade-in ${className}`}>
      {(title || actions) && (
        <header className="panel-head">
          {title ? <h2 className="panel-title">{title}</h2> : <span />}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-muted" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </span>
  );
}

export function Skeleton({ className = 'h-4 w-full' }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`animate-shimmer rounded bg-[length:800px_100%] bg-gradient-to-r from-raised via-line to-raised ${className}`}
    />
  );
}

export function LoadingBlock({ rows = 3, label }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-2" aria-busy="true">
      {label && <Spinner label={label} />}
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`h-4 ${i % 2 ? 'w-3/4' : 'w-full'}`} />
      ))}
    </div>
  );
}

export function ErrorNotice({
  error,
  onRetry,
  compact = false,
}: {
  error: unknown;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const apiError = error instanceof ApiError ? error : null;
  const needsAuth = apiError?.status === 401;
  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded border border-down/30 bg-down/5 ${compact ? 'px-3 py-2' : 'p-4'} text-sm`}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-down" aria-hidden />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-ink">{describeError(error)}</p>
        {apiError?.requestId && !compact && (
          <p className="num text-2xs text-ink-faint">request id {apiError.requestId}</p>
        )}
        {needsAuth && (
          <Link href="/login" className="text-accent underline-offset-2 hover:underline">
            Sign in
          </Link>
        )}
      </div>
      {onRetry && !needsAuth && (
        <button type="button" onClick={onRetry} className="btn-ghost shrink-0 px-2 py-1 text-xs">
          <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      {icon && <div className="text-ink-faint">{icon}</div>}
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <div className="max-w-md text-sm text-ink-muted">{children}</div>}
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}

export function Notes({
  items,
  tone = 'warn',
  title,
}: {
  items: string[];
  tone?: 'warn' | 'info';
  title?: string;
}) {
  if (!items.length) return null;
  const color = tone === 'warn' ? 'border-warn/30 bg-warn/5' : 'border-info/30 bg-info/5';
  const Icon = tone === 'warn' ? AlertTriangle : Info;
  return (
    <div className={`rounded border ${color} px-3 py-2 text-sm`}>
      {title && (
        <p className={`mb-1 flex items-center gap-1.5 text-xs font-semibold ${tone === 'warn' ? 'text-warn' : 'text-info'}`}>
          <Icon className="h-3.5 w-3.5" aria-hidden /> {title}
        </p>
      )}
      <ul className="space-y-1 text-ink-muted">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2">
            <span className="text-ink-faint" aria-hidden>
              ·
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  size = 'sm',
}: {
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  size?: 'xs' | 'sm';
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap items-center gap-0.5">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={`rounded font-medium transition-colors ${size === 'xs' ? 'px-1.5 py-0.5 text-xs' : 'px-2.5 py-1 text-[13px]'} ${
              active ? 'bg-raised text-ink' : 'text-ink-muted hover:bg-raised/60 hover:text-ink'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/** Underline tabs (TradingView / Kite style). */
export function Tabs<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="tabs">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          onClick={() => onChange(option.value)}
          className="tab"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/**
 * One analysis section: a heading, a plain-language explanation of what the
 * chart measures, the reading for this asset, then the chart itself at full
 * width. Explanations restate backend numbers; they never compute metrics.
 */
export function AnalysisSection({
  id,
  title,
  what,
  reading,
  aside,
  children,
}: {
  id?: string;
  title: string;
  what: React.ReactNode;
  reading?: React.ReactNode;
  aside?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <section id={id} aria-label={title} className="animate-fade-in border-t border-line pt-6 first:border-t-0 first:pt-0">
      <div className="grid gap-x-8 gap-y-3 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-2">
          <h2 className="section-title">{title}</h2>
          <p className="prose-explain">{what}</p>
          {reading && (
            <p className="rounded border-l-2 border-accent bg-accent/5 px-3 py-2 text-[13px] leading-relaxed text-ink">{reading}</p>
          )}
        </div>
        {aside && <div className="lg:pt-1">{aside}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </section>
  );
}

/** Compact label / value list used for statistics (Kite-style). */
export function StatList({ rows }: { rows: { label: string; value: React.ReactNode; tone?: string; hint?: string }[] }) {
  return (
    <dl className="divide-y divide-line/60 text-[13px]">
      {rows.map((row) => (
        <div key={row.label} className="flex items-baseline justify-between gap-4 py-1.5" title={row.hint}>
          <dt className="text-ink-muted">{row.label}</dt>
          <dd className={`num text-right font-medium ${row.tone ?? 'text-ink'}`}>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
