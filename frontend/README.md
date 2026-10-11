# ARGUS frontend

Next.js 14 (App Router) + TypeScript + Tailwind, built as a **static export**
(`output: 'export'`). The export is served by the FastAPI backend from
`backend/app/static`, so the UI and the API share one origin in production.
During development, `next dev` runs on :3000 and talks to the API on :8000.

## Commands

```bash
npm ci              # install exact versions from package-lock.json
npm run dev         # http://localhost:3000 (expects the API on :8000)
npm run typecheck   # tsc --noEmit
npm run lint        # next lint (next/core-web-vitals)
npm test            # vitest run: unit tests in tests/
npm run build       # static export to out/
npm run export:backend  # copy out/ into backend/app/static (replaces it)
npm run test:e2e    # Playwright browser tests (build + export:backend first; see e2e/)
```

From the repo root, `npm run build` does install + build + copy in one step.

## Pages

Dynamic pages use query parameters (`/asset?symbol=AAPL`) because a static
export cannot pre-render arbitrary `[symbol]` routes.

| Route | Purpose |
|---|---|
| `/` | Overview: market snapshot (SPY, QQQ, IWM, TLT, GLD), watchlist, recent research, backend capabilities |
| `/asset?symbol=X[&tab=analytics\|news\|filings]` | Quote header with freshness badge, price/volume chart (1M–max), profile and provider statistics, full analytics (return/risk/relative metrics, cumulative vs benchmark, drawdown, rolling volatility and beta, return distribution), news, SEC filings |
| `/portfolio[?add=X]` | Holdings editor (weights in %), daily-rebalanced vs buy-and-hold, results (metrics, growth vs benchmark, drawdown, weight vs risk contribution, correlation heatmap, per-holding table, assumptions), historical stress episodes, saved portfolios with optimistic-concurrency updates |
| `/research[?symbol=X\|?id=…]` | Streamed (SSE) multi-agent report with per-stage progress and cancel; claims labelled Fact/Analysis with clickable evidence citations; evidence panel (metrics, quotes, headlines, document passages with "open at page N"); limitations, validation counts and rejected claims, execution trace, JSON export; saved history |
| `/documents` | Upload (PDF/TXT/MD/HTML ≤ 15 MB), library with status, delete, passage search with relevance scores and an explicit insufficient-evidence state, SEC filing import |
| `/login` | Sign in / create account (HttpOnly session cookie) |
| `/settings` | Backend URL (per-browser), capabilities, metric definitions from `/api/meta/metrics` |
| `/analyze` | Legacy route; redirects to `/asset?…&tab=analytics` |

## Design rules the code follows

- **No financial math in the browser.** Every metric comes from the API.
  The browser only formats numbers (and bins daily returns for the histogram).
- **Undefined is not zero.** `null` metrics render as `—`, with the reason
  where the API gives one.
- **Freshness is always visible.** `DataBadge` shows Delayed / End of day /
  Synthetic / Stale from each payload's `provenance`. Nothing is labelled
  real-time. Fixture mode shows a site-wide "not market prices" banner.
- **One network path.** `lib/api.ts` handles base-URL resolution,
  `credentials: 'include'`, the `X-ARGUS-CSRF` header on mutating requests,
  timeouts, and the backend's error envelope (`ApiError` with code, request id,
  and Retry-After).
- **Third-party text is data.** Headlines and document passages are rendered
  as text (never HTML) and marked "third-party" in the evidence panel.
- Local storage is only used for conveniences (backend URL, recent symbols,
  unsaved portfolio draft), wrapped in try/catch.

## Structure

```
app/            routes (each page is a client component)
components/     AppShell, SymbolSearch, DataBadge, MetricGrid, QuoteTable, ui primitives
components/charts/  TimeSeriesChart (lightweight-charts), Heatmap, BarRows
components/asset|portfolio|research/  page-specific panels
lib/            api client, types (mirror backend schemas), formatting, SSE parser,
                auth/system/metric-definition contexts, holdings validation
tests/          vitest unit tests (api client, SSE parsing, formatting, holdings rules)
```

## Known limitations

- Browser tests run against fixture data only. Live Yahoo data and model
  synthesis are covered by manual checks and backend tests, not by Playwright.
- Charts are client-rendered; the static HTML contains only page shells.
- Dark theme only.
