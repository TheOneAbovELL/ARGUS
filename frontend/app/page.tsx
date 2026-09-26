'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { checkHealth } from '@/lib/api';

export default function Home() {
  const [status, setStatus] = useState<'checking' | 'ok' | 'error'>('checking');

  useEffect(() => {
    checkHealth()
      .then((res) => {
        if (res.status === 'ok') setStatus('ok');
        else setStatus('error');
      })
      .catch(() => setStatus('error'));
  }, []);

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] text-center space-y-12">
      <div className="space-y-4">
        <h1 className="text-6xl font-bold font-mono tracking-widest text-argus-text">
          <span className="text-argus-accent">ARGUS</span>
        </h1>
        <p className="text-xl text-argus-muted max-w-2xl mx-auto">
          Advanced Quantitative Finance Research Platform
        </p>
      </div>

      <div className="flex items-center space-x-3 font-mono">
        <div className="text-sm text-argus-muted uppercase">Backend Status:</div>
        {status === 'checking' && <div className="text-yellow-500">Checking...</div>}
        {status === 'ok' && <div className="text-argus-accent flex items-center"><span className="w-2 h-2 rounded-full bg-argus-accent mr-2"></span>Connected</div>}
        {status === 'error' && <div className="text-argus-error flex items-center"><span className="w-2 h-2 rounded-full bg-argus-error mr-2"></span>Disconnected</div>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
        <Link href="/analyze" className="group p-6 bg-argus-surface border border-argus-border rounded-lg hover:border-argus-accent transition-colors text-left">
          <h2 className="text-xl font-bold text-argus-accent mb-2 font-mono group-hover:text-argus-secondary transition-colors">/analyze</h2>
          <p className="text-argus-muted text-sm">Full quantitative analysis for individual assets including returns, volatility, sharpe ratio, beta, and drawdown metrics.</p>
        </Link>
        <Link href="/portfolio" className="group p-6 bg-argus-surface border border-argus-border rounded-lg hover:border-argus-accent transition-colors text-left">
          <h2 className="text-xl font-bold text-argus-accent mb-2 font-mono group-hover:text-argus-secondary transition-colors">/portfolio</h2>
          <p className="text-argus-muted text-sm">Analyze custom portfolios with weighted holdings against benchmarks and compare multiple tickers side-by-side.</p>
        </Link>
        <Link href="/research" className="group p-6 bg-argus-surface border border-argus-border rounded-lg hover:border-argus-accent transition-colors text-left">
          <h2 className="text-xl font-bold text-argus-accent mb-2 font-mono group-hover:text-argus-secondary transition-colors">/research</h2>
          <p className="text-argus-muted text-sm">Generate AI-driven research reports and ingest custom documents for advanced RAG analysis.</p>
        </Link>
      </div>
    </div>
  );
}
