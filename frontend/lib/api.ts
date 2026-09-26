export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─── Health ──────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Backend unavailable');
  return res.json();
}

// ─── Analyze ─────────────────────────────────────────────────

export interface QuantMetrics {
  annual_return: number;
  volatility: number;
  sharpe_ratio: number;
  beta: number;
  max_drawdown: number;
}

export interface AnalyzeResponse {
  ticker: string;
  company_name: string;
  sector: string;
  current_price: number;
  metrics: QuantMetrics;
}

export async function analyzeTicker(ticker: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to analyze ticker');
  }
  return res.json();
}

// ─── Portfolio ───────────────────────────────────────────────

export interface PortfolioHolding {
  ticker: string;
  weight: number; // 0–100, must sum to 100
}

export interface PortfolioAnalysisResponse {
  portfolio_return: number;
  portfolio_volatility: number;
  portfolio_sharpe: number;
  portfolio_beta: number;
  portfolio_drawdown: number;
  holdings: PortfolioHolding[];
}

export async function analyzePortfolio(
  holdings: PortfolioHolding[],
): Promise<PortfolioAnalysisResponse> {
  const res = await fetch(`${API_BASE}/portfolio/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ holdings }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to analyze portfolio');
  }
  return res.json();
}

// ─── Research ────────────────────────────────────────────────

export interface DocumentSource {
  title: string;
  document_type: string;
  source: string;
  page_number: number;
  chunk_id: string;
  score: number;
}

export interface ResearchResponse {
  market_summary: string;
  risk_summary: string;
  news_summary: string;
  bull_case: string;
  bear_case: string;
  neutral_case: string;
  key_risks: string[];
  key_opportunities: string[];
  document_insights: string[];
  sources: DocumentSource[];
}

export async function researchTicker(ticker: string): Promise<ResearchResponse> {
  const res = await fetch(`${API_BASE}/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to generate research report');
  }
  return res.json();
}
