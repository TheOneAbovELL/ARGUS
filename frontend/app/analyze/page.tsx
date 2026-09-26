'use client';
import { useState } from 'react';
import { analyzeTicker, AnalyzeResponse } from '@/lib/api';
import MetricCard from '@/components/MetricCard';
import LoadingSpinner from '@/components/LoadingSpinner';

export default function AnalyzePage() {
  const [ticker, setTicker] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<AnalyzeResponse | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker) return;

    setLoading(true);
    setError('');
    setData(null);

    try {
      const result = await analyzeTicker(ticker.toUpperCase());
      setData(result);
    } catch (err: any) {
      setError(err.message || 'An error occurred during analysis');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="bg-argus-surface border border-argus-border rounded-lg p-6">
        <h2 className="text-xl font-mono text-argus-accent mb-4 uppercase tracking-wider">Asset Analysis</h2>
        <form onSubmit={handleAnalyze} className="flex space-x-4">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Enter Ticker (e.g. AAPL)"
            className="flex-1 bg-argus-bg border border-argus-border rounded px-4 py-2 text-argus-text font-mono focus:outline-none focus:border-argus-accent uppercase placeholder:normal-case"
          />
          <button
            type="submit"
            disabled={loading || !ticker}
            className="bg-argus-accent text-argus-bg px-6 py-2 rounded font-bold font-mono hover:bg-argus-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            ANALYZE
          </button>
        </form>
        {error && <div className="mt-4 text-argus-error font-mono text-sm">{error}</div>}
      </div>

      {loading && <LoadingSpinner />}

      {data && !loading && (
        <div className="space-y-8">
          <div className="bg-argus-surface border border-argus-border rounded-lg p-6">
            <div className="flex items-baseline justify-between mb-4">
              <h3 className="text-2xl font-mono text-white">
                <span className="text-argus-secondary">{data.ticker}</span>
                <span className="text-argus-muted text-sm ml-3">{data.company_name}</span>
              </h3>
              <div className="text-right">
                <div className="text-argus-muted text-xs font-mono uppercase">Current Price</div>
                <div className="text-argus-accent text-2xl font-mono font-bold">${data.current_price.toFixed(2)}</div>
              </div>
            </div>
            <div className="text-argus-muted text-sm font-mono">Sector: {data.sector}</div>
          </div>

          <div className="space-y-4">
            <h4 className="text-sm font-mono text-argus-muted uppercase border-b border-argus-border pb-2">Quantitative Metrics</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <MetricCard title="Annual Return" value={data.metrics.annual_return} isPercentage />
              <MetricCard title="Volatility" value={data.metrics.volatility} isPercentage />
              <MetricCard title="Sharpe Ratio" value={data.metrics.sharpe_ratio} />
              <MetricCard title="Beta" value={data.metrics.beta} subtitle="vs SPY" />
              <MetricCard title="Max Drawdown" value={data.metrics.max_drawdown} isPercentage />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
