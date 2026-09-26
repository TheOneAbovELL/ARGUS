'use client';
import { useState } from 'react';
import { analyzePortfolio, PortfolioHolding, PortfolioAnalysisResponse } from '@/lib/api';
import MetricCard from '@/components/MetricCard';
import LoadingSpinner from '@/components/LoadingSpinner';

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([{ ticker: '', weight: 50 }, { ticker: '', weight: 50 }]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<PortfolioAnalysisResponse | null>(null);

  const totalWeight = holdings.reduce((sum, h) => sum + (Number(h.weight) || 0), 0);

  const handleAddHolding = () => setHoldings([...holdings, { ticker: '', weight: 0 }]);
  const handleRemoveHolding = (index: number) => {
    const newHoldings = [...holdings];
    newHoldings.splice(index, 1);
    setHoldings(newHoldings);
  };
  const handleHoldingChange = (index: number, field: keyof PortfolioHolding, value: string) => {
    const newHoldings = [...holdings];
    if (field === 'weight') {
      newHoldings[index].weight = Number(value);
    } else {
      newHoldings[index].ticker = value.toUpperCase();
    }
    setHoldings(newHoldings);
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (Math.abs(totalWeight - 100) > 0.01) {
      setError('Weights must sum to 100%');
      return;
    }
    const validHoldings = holdings.filter(h => h.ticker.trim() !== '');
    if (validHoldings.length < 1) {
      setError('Add at least one holding with a ticker');
      return;
    }
    setLoading(true);
    setError('');
    setData(null);
    try {
      const result = await analyzePortfolio(validHoldings);
      setData(result);
    } catch (err: any) {
      setError(err.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-argus-surface border border-argus-border rounded-lg p-6">
        <h2 className="text-xl font-mono text-argus-accent mb-4 uppercase tracking-wider">Portfolio Analysis</h2>
        <form onSubmit={handleAnalyze} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-mono text-argus-muted uppercase">Holdings (weights must sum to 100)</label>
            {holdings.map((holding, i) => (
              <div key={i} className="flex space-x-4 items-center">
                <input
                  type="text"
                  placeholder="Ticker"
                  value={holding.ticker}
                  onChange={(e) => handleHoldingChange(i, 'ticker', e.target.value)}
                  className="flex-1 bg-argus-bg border border-argus-border rounded px-4 py-2 text-argus-text font-mono focus:border-argus-accent focus:outline-none uppercase"
                />
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    placeholder="Weight"
                    value={holding.weight}
                    onChange={(e) => handleHoldingChange(i, 'weight', e.target.value)}
                    className="w-32 bg-argus-bg border border-argus-border rounded px-4 py-2 text-argus-text font-mono focus:border-argus-accent focus:outline-none"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-argus-muted font-mono text-sm">%</span>
                </div>
                {holdings.length > 1 && (
                  <button type="button" onClick={() => handleRemoveHolding(i)} className="text-argus-error px-3 py-2 hover:bg-argus-error/10 rounded">✕</button>
                )}
              </div>
            ))}
            <div className="flex justify-between items-center mt-2">
              <button type="button" onClick={handleAddHolding} className="text-argus-secondary text-sm font-mono hover:underline">+ Add Holding</button>
              <div className={`text-sm font-mono ${Math.abs(totalWeight - 100) > 0.01 ? 'text-argus-error' : 'text-argus-accent'}`}>
                Total: {totalWeight.toFixed(1)}%
              </div>
            </div>
          </div>

          <button type="submit" disabled={loading} className="w-full bg-argus-accent text-argus-bg px-6 py-2 rounded font-bold font-mono hover:bg-argus-secondary transition-colors disabled:opacity-50">
            ANALYZE PORTFOLIO
          </button>
          {error && <div className="text-argus-error font-mono text-sm">{error}</div>}
        </form>
      </div>

      {loading && <LoadingSpinner />}

      {data && !loading && (
        <div className="space-y-6">
          <div className="space-y-4">
            <h4 className="text-sm font-mono text-argus-muted uppercase border-b border-argus-border pb-2">Portfolio Metrics</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <MetricCard title="Portfolio Return" value={data.portfolio_return} isPercentage />
              <MetricCard title="Portfolio Volatility" value={data.portfolio_volatility} isPercentage />
              <MetricCard title="Portfolio Sharpe" value={data.portfolio_sharpe} />
              <MetricCard title="Portfolio Beta" value={data.portfolio_beta} />
              <MetricCard title="Portfolio Drawdown" value={data.portfolio_drawdown} isPercentage />
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-sm font-mono text-argus-muted uppercase border-b border-argus-border pb-2">Analyzed Holdings</h4>
            <div className="bg-argus-surface border border-argus-border rounded-lg overflow-hidden">
              <table className="w-full font-mono text-sm">
                <thead>
                  <tr className="border-b border-argus-border text-argus-muted text-left">
                    <th className="px-4 py-3">Ticker</th>
                    <th className="px-4 py-3 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {data.holdings.map((h, i) => (
                    <tr key={i} className="border-b border-argus-border/50">
                      <td className="px-4 py-3 text-argus-secondary">{h.ticker}</td>
                      <td className="px-4 py-3 text-right text-argus-text">{h.weight.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
