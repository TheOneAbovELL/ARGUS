'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { checkHealth, getApiBase, setCustomApiBase } from '@/lib/api';

export default function Home() {
  const [status, setStatus] = useState<'checking' | 'ok' | 'error'>('checking');
  const [currentBase, setCurrentBase] = useState<string>('');
  const [inputUrl, setInputUrl] = useState<string>('');
  const [showConfig, setShowConfig] = useState(false);
  const [testMsg, setTestMsg] = useState('');

  const refreshStatus = (targetUrl?: string) => {
    setStatus('checking');
    setTestMsg('');
    const baseToTest = targetUrl !== undefined ? targetUrl : getApiBase();
    checkHealth(baseToTest)
      .then((res) => {
        if (res.status === 'ok') {
          setStatus('ok');
          setCurrentBase(baseToTest || 'Same Origin (Unified)');
        } else {
          setStatus('error');
        }
      })
      .catch(() => {
        setStatus('error');
        setCurrentBase(baseToTest || 'Same Origin (Unified)');
      });
  };

  useEffect(() => {
    const base = getApiBase();
    setCurrentBase(base || 'Same Origin (Unified)');
    setInputUrl(base || '');
    refreshStatus(base);
  }, []);

  const handleSaveUrl = (e: React.FormEvent) => {
    e.preventDefault();
    setCustomApiBase(inputUrl);
    refreshStatus(inputUrl);
    setTestMsg('Saved! Testing connection...');
  };

  const handleReset = () => {
    setCustomApiBase('');
    setInputUrl('');
    refreshStatus('');
    setTestMsg('Reset to default auto-detect.');
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] text-center space-y-10">
      <div className="space-y-4">
        <h1 className="text-6xl font-bold font-mono tracking-widest text-argus-text">
          <span className="text-argus-accent">ARGUS</span>
        </h1>
        <p className="text-xl text-argus-muted max-w-2xl mx-auto">
          AI-Powered Quantitative Research Terminal & Analytics Engine
        </p>
      </div>

      <div className="flex flex-col items-center space-y-3 font-mono">
        <div className="flex items-center space-x-3 bg-argus-surface border border-argus-border px-4 py-2 rounded-full">
          <span className="text-xs text-argus-muted uppercase">Backend Status:</span>
          {status === 'checking' && <span className="text-yellow-400 text-sm animate-pulse">Checking...</span>}
          {status === 'ok' && (
            <span className="text-argus-accent text-sm flex items-center">
              <span className="w-2.5 h-2.5 rounded-full bg-argus-accent mr-2 inline-block"></span>
              Connected ({currentBase})
            </span>
          )}
          {status === 'error' && (
            <span className="text-argus-error text-sm flex items-center">
              <span className="w-2.5 h-2.5 rounded-full bg-argus-error mr-2 inline-block"></span>
              Disconnected
            </span>
          )}
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="text-xs text-argus-secondary hover:underline ml-2"
          >
            {showConfig ? '[Hide Config]' : '[Configure Connection]'}
          </button>
        </div>

        {showConfig && (
          <form onSubmit={handleSaveUrl} className="bg-argus-surface border border-argus-border p-4 rounded-lg text-left max-w-lg w-full space-y-3 text-xs">
            <div className="text-argus-muted">
              <strong>Connection Settings:</strong> In unified deployment, backend is auto-detected. If your frontend and backend are on different URLs (e.g. Vercel + Render), paste your backend URL below.
            </div>
            <div className="flex space-x-2">
              <input
                type="text"
                placeholder="e.g. https://your-backend.onrender.com or http://localhost:8000"
                value={inputUrl}
                onChange={(e) => setInputUrl(e.target.value)}
                className="flex-1 bg-argus-bg border border-argus-border rounded px-3 py-1.5 text-argus-text focus:border-argus-accent focus:outline-none"
              />
              <button
                type="submit"
                className="bg-argus-accent text-argus-bg px-3 py-1.5 rounded font-bold hover:bg-argus-secondary transition-colors"
              >
                Connect
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="bg-argus-bg border border-argus-border text-argus-muted px-3 py-1.5 rounded hover:text-white"
              >
                Reset
              </button>
            </div>
            {testMsg && <div className="text-argus-secondary">{testMsg}</div>}
          </form>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
        <Link href="/analyze" className="group p-6 bg-argus-surface border border-argus-border rounded-lg hover:border-argus-accent transition-colors text-left">
          <h2 className="text-xl font-bold text-argus-accent mb-2 font-mono group-hover:text-argus-secondary transition-colors">/analyze</h2>
          <p className="text-argus-muted text-sm">Full quantitative analysis for individual assets including returns, volatility, sharpe ratio, beta, and drawdown metrics.</p>
        </Link>
        <Link href="/portfolio" className="group p-6 bg-argus-surface border border-argus-border rounded-lg hover:border-argus-accent transition-colors text-left">
          <h2 className="text-xl font-bold text-argus-accent mb-2 font-mono group-hover:text-argus-secondary transition-colors">/portfolio</h2>
          <p className="text-argus-muted text-sm">Analyze custom portfolios with weighted holdings against benchmarks and get full portfolio-level risk metrics.</p>
        </Link>
        <Link href="/research" className="group p-6 bg-argus-surface border border-argus-border rounded-lg hover:border-argus-accent transition-colors text-left">
          <h2 className="text-xl font-bold text-argus-accent mb-2 font-mono group-hover:text-argus-secondary transition-colors">/research</h2>
          <p className="text-argus-muted text-sm">Generate AI-driven research reports with market, risk, news summaries, and bull/bear/neutral investment cases.</p>
        </Link>
      </div>
    </div>
  );
}
