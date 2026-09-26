'use client';
import { useState } from 'react';
import { researchTicker, ResearchResponse } from '@/lib/api';
import LoadingSpinner from '@/components/LoadingSpinner';

export default function ResearchPage() {
  const [ticker, setTicker] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<ResearchResponse | null>(null);

  const handleResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker) return;
    setLoading(true);
    setError('');
    setData(null);
    try {
      const result = await researchTicker(ticker.toUpperCase());
      setData(result);
    } catch (err: any) {
      setError(err.message || 'Failed to generate research report');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-argus-surface border border-argus-border rounded-lg p-6">
        <h2 className="text-xl font-mono text-argus-accent mb-4 uppercase tracking-wider">Research Report</h2>
        <form onSubmit={handleResearch} className="flex space-x-4">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Enter Ticker (e.g. AAPL)"
            className="flex-1 bg-argus-bg border border-argus-border rounded px-4 py-2 text-argus-text font-mono focus:outline-none focus:border-argus-accent uppercase placeholder:normal-case"
            required
          />
          <button
            type="submit"
            disabled={loading || !ticker}
            className="bg-argus-accent text-argus-bg px-6 py-2 rounded font-bold font-mono hover:bg-argus-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            RESEARCH
          </button>
        </form>
        {error && <div className="mt-4 text-argus-error font-mono text-sm">{error}</div>}
      </div>

      {loading && <LoadingSpinner />}

      {data && !loading && (
        <div className="space-y-6">
          {/* Investment Cases */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-green-400 uppercase tracking-wider mb-3 flex items-center">
                <span className="w-2 h-2 rounded-full bg-green-400 mr-2"></span>
                Bull Case
              </h4>
              <p className="text-argus-text text-sm leading-relaxed">{data.bull_case}</p>
            </div>
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-yellow-400 uppercase tracking-wider mb-3 flex items-center">
                <span className="w-2 h-2 rounded-full bg-yellow-400 mr-2"></span>
                Neutral Case
              </h4>
              <p className="text-argus-text text-sm leading-relaxed">{data.neutral_case}</p>
            </div>
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-red-400 uppercase tracking-wider mb-3 flex items-center">
                <span className="w-2 h-2 rounded-full bg-red-400 mr-2"></span>
                Bear Case
              </h4>
              <p className="text-argus-text text-sm leading-relaxed">{data.bear_case}</p>
            </div>
          </div>

          {/* Summaries */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-argus-secondary uppercase tracking-wider mb-3">Market Summary</h4>
              <p className="text-argus-text text-sm leading-relaxed">{data.market_summary}</p>
            </div>
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-argus-secondary uppercase tracking-wider mb-3">Risk Summary</h4>
              <p className="text-argus-text text-sm leading-relaxed">{data.risk_summary}</p>
            </div>
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-argus-secondary uppercase tracking-wider mb-3">News Summary</h4>
              <p className="text-argus-text text-sm leading-relaxed">{data.news_summary}</p>
            </div>
          </div>

          {/* Risks & Opportunities */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-red-400 uppercase tracking-wider mb-3">Key Risks</h4>
              {data.key_risks.length > 0 ? (
                <ul className="space-y-2">
                  {data.key_risks.map((risk, i) => (
                    <li key={i} className="text-argus-text text-sm flex items-start">
                      <span className="text-red-400 mr-2 mt-0.5">▸</span>
                      {risk}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-argus-muted text-sm italic">No risks identified</p>
              )}
            </div>
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-green-400 uppercase tracking-wider mb-3">Key Opportunities</h4>
              {data.key_opportunities.length > 0 ? (
                <ul className="space-y-2">
                  {data.key_opportunities.map((opp, i) => (
                    <li key={i} className="text-argus-text text-sm flex items-start">
                      <span className="text-green-400 mr-2 mt-0.5">▸</span>
                      {opp}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-argus-muted text-sm italic">No opportunities identified</p>
              )}
            </div>
          </div>

          {/* Document Insights */}
          {data.document_insights.length > 0 && (
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-argus-secondary uppercase tracking-wider mb-3">Document Insights</h4>
              <ul className="space-y-2">
                {data.document_insights.map((insight, i) => (
                  <li key={i} className="text-argus-text text-sm flex items-start">
                    <span className="text-argus-accent mr-2 mt-0.5">▸</span>
                    {insight}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Sources */}
          {data.sources.length > 0 && (
            <div className="bg-argus-surface border border-argus-border rounded-lg p-5">
              <h4 className="text-sm font-mono text-argus-secondary uppercase tracking-wider mb-3">Sources</h4>
              <div className="overflow-x-auto">
                <table className="w-full font-mono text-xs">
                  <thead>
                    <tr className="border-b border-argus-border text-argus-muted text-left">
                      <th className="px-3 py-2">Title</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Source</th>
                      <th className="px-3 py-2 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sources.map((src, i) => (
                      <tr key={i} className="border-b border-argus-border/50">
                        <td className="px-3 py-2 text-argus-text">{src.title}</td>
                        <td className="px-3 py-2 text-argus-muted">{src.document_type}</td>
                        <td className="px-3 py-2 text-argus-muted">{src.source}</td>
                        <td className="px-3 py-2 text-argus-accent text-right">{src.score.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
