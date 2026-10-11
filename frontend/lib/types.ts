// Types mirroring the backend contract (backend/app/schemas/*).
// Percent-like numbers are DECIMALS (0.12 = 12%). Undefined metrics are null.

export type DataMode = 'delayed' | 'end_of_day' | 'fixture';

export interface Provenance {
  provider: string;
  mode: DataMode;
  retrieved_at: string;
  as_of: string | null;
  cached: boolean;
  stale: boolean;
}

export interface SymbolMatch {
  symbol: string;
  name: string;
  exchange: string | null;
  quote_type: string | null;
}

export interface Quote {
  symbol: string;
  name: string;
  price: number;
  previous_close: number | null;
  change: number | null;
  change_percent: number | null;
  currency: string | null;
  exchange: string | null;
  quote_type: string | null;
  market_state: string | null;
  provenance: Provenance;
}

export interface QuoteResult {
  symbol: string;
  quote: Quote | null;
  error: string | null;
}

export interface KeyStat {
  key: string;
  label: string;
  value: number | null;
  unit: 'currency' | 'percent' | 'ratio' | 'count';
  currency: string | null;
}

export interface Profile {
  symbol: string;
  name: string;
  quote_type: string | null;
  exchange: string | null;
  currency: string | null;
  sector: string | null;
  industry: string | null;
  country: string | null;
  website: string | null;
  summary: string | null;
  stats: KeyStat[];
  provenance: Provenance;
}

export interface History {
  symbol: string;
  currency: string | null;
  dates: string[];
  open: (number | null)[];
  high: (number | null)[];
  low: (number | null)[];
  close: number[];
  adj_close: number[];
  volume: (number | null)[];
  actions: { date: string; kind: 'dividend' | 'split'; value: number }[];
  quality_notes: string[];
  provenance: Provenance;
}

export type IndicatorKey =
  | 'sma20' | 'sma50' | 'sma200' | 'ema20'
  | 'bb_upper' | 'bb_middle' | 'bb_lower'
  | 'rsi14' | 'macd' | 'macd_signal' | 'macd_hist'
  | 'atr14' | 'volume_sma20';

export interface TechnicalSignal {
  key: string;
  label: string;
  value: string;
  tone: 'positive' | 'negative' | 'neutral';
  reading: string;
  method: string;
}

/** Daily bars + indicators aligned to `dates` (null = warm-up / undefined). */
export interface Technicals {
  symbol: string;
  currency: string | null;
  window: { start: string; end: string; label: string };
  dates: string[];
  open: (number | null)[];
  high: (number | null)[];
  low: (number | null)[];
  close: number[];
  volume: (number | null)[];
  indicators: Record<IndicatorKey, (number | null)[]>;
  signals: TechnicalSignal[];
  high_52w: number | null;
  low_52w: number | null;
  last_close: number;
  as_of: string;
  default_benchmark: string;
  quality_notes: string[];
  provenance: Provenance;
  conventions: string;
}

export interface NewsItem {
  id: string;
  title: string;
  publisher: string;
  url: string | null;
  published_at: string | null;
  related_symbols: string[];
}

export interface NewsFeed {
  symbol: string;
  items: NewsItem[];
  provenance: Provenance;
}

export interface Performance {
  observations: number;
  total_return: number;
  annualized_return: number | null;
  annualized_volatility: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number;
  max_drawdown_peak: string;
  max_drawdown_trough: string;
  max_drawdown_recovery: string | null;
  longest_drawdown_days: number;
  current_drawdown: number;
  var_95: number | null;
  cvar_95: number | null;
  best_period: number;
  worst_period: number;
  positive_periods_ratio: number;
}

export interface Relative {
  observations: number;
  beta: number | null;
  alpha: number | null;
  correlation: number | null;
  r_squared: number | null;
  tracking_error: number | null;
  information_ratio: number | null;
  benchmark_total_return: number;
  benchmark_annualized_return: number | null;
  excess_annualized_return: number | null;
}

export interface Window {
  start: string;
  end: string;
  label: string;
}

export interface AssetAnalysis {
  symbol: string;
  benchmark: string;
  currency: string | null;
  benchmark_currency: string | null;
  window: Window;
  periods_per_year: number;
  risk_free_rate: number;
  performance: Performance;
  relative: Relative | null;
  series: {
    dates: string[];
    close: number[];
    adj_close: number[];
    drawdown: number[];
    rolling_volatility: (number | null)[];
    daily_returns: number[];
  };
  comparison: {
    dates: string[];
    asset_cumulative: number[];
    benchmark_cumulative: number[];
    rolling_beta: (number | null)[];
  } | null;
  warnings: string[];
  provenance: Record<string, Provenance>;
}

export type RebalancingModel = 'daily_rebalanced' | 'buy_and_hold';

export interface HoldingInput {
  symbol: string;
  weight: number; // percent
}

export interface AssetContribution {
  symbol: string;
  weight: number;
  ending_weight: number;
  total_return: number;
  annualized_return: number | null;
  annualized_volatility: number | null;
  beta: number | null;
  return_contribution: number;
  risk_contribution: number | null;
  marginal_risk: number | null;
}

export interface PortfolioAnalysis {
  model: RebalancingModel;
  benchmark: string;
  start: string;
  end: string;
  periods_per_year: number;
  risk_free_rate: number;
  performance: Performance;
  relative: Relative | null;
  assets: AssetContribution[];
  correlation_symbols: string[];
  correlation: (number | null)[][];
  diversification_ratio: number | null;
  contribution_method: string;
  series: {
    dates: string[];
    cumulative_return: number[];
    drawdown: number[];
    benchmark_dates: string[];
    benchmark_cumulative_return: number[];
    portfolio_cumulative_on_benchmark_dates: number[];
  };
  warnings: string[];
  assumptions: string[];
  provenance: Record<string, Provenance>;
}

export interface StressEpisode {
  key: string;
  name: string;
  start: string;
  end: string;
  description: string;
  computable: boolean;
  portfolio_return: number | null;
  benchmark_return: number | null;
  portfolio_max_drawdown: number | null;
  missing_symbols: string[];
}

export interface StressResult {
  benchmark: string;
  method: string;
  episodes: StressEpisode[];
}

export interface PageMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface SavedPortfolio {
  id: string;
  name: string;
  description: string | null;
  benchmark: string;
  rebalancing: RebalancingModel;
  holdings: HoldingInput[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
}

export interface SessionInfo {
  user: User;
  expires_at: string;
}

export interface WatchlistItem {
  symbol: string;
  created_at: string;
}

export type ClaimKind = 'fact' | 'interpretation';

export interface Claim {
  text: string;
  kind: ClaimKind;
  evidence_ids: string[];
  /** "model": proposed by the language model; "agent": ARGUS's rule-based agents. */
  origin?: 'model' | 'agent';
}

export interface ReportSection {
  key: string;
  title: string;
  claims: Claim[];
}

export interface EvidenceItem {
  id: string;
  kind: 'quote' | 'profile' | 'metric' | 'news' | 'document' | 'method';
  label: string;
  statement: string;
  source: string;
  as_of: string | null;
  value: number | null;
  unit: string | null;
  url: string | null;
  document_id: string | null;
  page_number: number | null;
  chunk_id: string | null;
  retrieval_score: number | null;
  untrusted: boolean;
}

export interface ResearchReport {
  id?: string | null;
  saved?: boolean;
  symbol: string;
  name: string | null;
  question: string | null;
  generated_at: string;
  window: {
    label?: string;
    start?: string;
    end?: string;
    benchmark?: string;
    risk_free_rate?: number;
    observations?: number;
  };
  sections: ReportSection[];
  scenarios: ReportSection[];
  evidence: EvidenceItem[];
  limitations: string[];
  generation: {
    mode: 'deterministic' | 'llm';
    provider: string | null;
    model: string | null;
    fallback_reason: string | null;
    input_tokens: number | null;
    output_tokens: number | null;
    validation: {
      claims_total: number;
      claims_accepted: number;
      claims_rejected: number;
      claims_backfilled?: number;
      rejected: { section: string; text: string; reasons: string[] }[];
    };
  };
  trace: { step: string; status: string; duration_ms: number; detail: string | null }[];
  disclaimer: string;
}

export interface ResearchSummary {
  id: string;
  symbol: string;
  name: string | null;
  question: string | null;
  generation_mode: string;
  created_at: string;
  claims: number;
}

export interface ResearchStep {
  type: 'step';
  step: string;
  status: 'ok' | 'partial' | 'failed' | 'skipped' | 'running';
  detail: string | null;
}

export type DocumentType =
  | '10-K'
  | '10-Q'
  | '8-K'
  | '20-F'
  | 'annual_report'
  | 'earnings_call'
  | 'investor_presentation'
  | 'research_note'
  | 'other';

export interface DocumentRecord {
  id: string;
  symbol: string;
  title: string;
  document_type: DocumentType;
  source: string;
  filename: string | null;
  size_bytes: number;
  page_count: number;
  chunk_count: number;
  status: 'processing' | 'ready' | 'failed';
  error: string | null;
  published_on: string | null;
  created_at: string;
}

export interface Passage {
  chunk_id: string;
  document_id: string;
  title: string;
  document_type: string;
  source: string;
  page_number: number;
  text: string;
  score: number;
  dense_score: number;
  lexical_score: number;
  published_on: string | null;
}

export interface SystemStatus {
  version: string;
  environment: string;
  market_data: { provider: string; mode: 'fixture' | 'delayed'; note: string };
  research: {
    mode: 'deterministic' | 'llm';
    llm_provider: string | null;
    llm_model: string | null;
    llm_host?: string | null;
    llm_local?: boolean | null;
  };
  embeddings: EmbeddingsStatus;
  sec_edgar: boolean;
}

export interface MetricDefinition {
  key: string;
  label: string;
  unit: string;
  formula: string;
  notes: string;
}

export interface Filing {
  form: string;
  accession: string;
  filed_on: string;
  report_date: string | null;
  company: string;
  url: string;
}

export interface EmbeddingsStatus {
  provider: 'onnx' | 'hash' | string;
  ready: boolean;
  status: 'not_started' | 'downloading' | 'ready' | 'failed' | string;
  downloaded_mb?: number | null;
  total_mb?: number | null;
  note?: string | null;
}
