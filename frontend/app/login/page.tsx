'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { describeError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Panel, SegmentedControl, Spinner } from '@/components/ui';

const MODES = [
  { value: 'login', label: 'Sign in' },
  { value: 'signup', label: 'Create account' },
] as const;

export default function LoginPage() {
  const router = useRouter();
  const { user, login, signup } = useAuth();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) router.replace('/');
  }, [user, router]);

  const passwordTooShort = mode === 'signup' && password.length > 0 && password.length < 10;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (passwordTooShort) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === 'login') await login(email, password);
      else await signup(email, password, displayName.trim() || undefined);
      router.replace('/');
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm pt-10">
      <Panel>
        <div className="space-y-4">
          <div>
            <h1 className="text-lg font-semibold">{mode === 'login' ? 'Sign in to ARGUS' : 'Create your ARGUS account'}</h1>
            <p className="mt-1 text-xs text-ink-muted">Accounts keep portfolios, watchlists, research history and documents private to you.</p>
          </div>
          <SegmentedControl label="Account action" options={MODES} value={mode} onChange={(m) => { setMode(m); setError(null); }} />
          <form onSubmit={submit} className="space-y-3">
            {mode === 'signup' && (
              <div>
                <label className="label" htmlFor="name">
                  Display name <span className="normal-case tracking-normal text-ink-faint">(optional)</span>
                </label>
                <input id="name" className="input" maxLength={80} value={displayName} onChange={(e) => setDisplayName(e.target.value)} autoComplete="nickname" />
              </div>
            )}
            <div>
              <label className="label" htmlFor="email">
                Email
              </label>
              <input id="email" type="email" className="input" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </div>
            <div>
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className={`input ${passwordTooShort ? 'border-down' : ''}`}
                required
                minLength={mode === 'signup' ? 10 : 1}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
              {mode === 'signup' && <p className={`mt-1 text-2xs ${passwordTooShort ? 'text-down' : 'text-ink-faint'}`}>At least 10 characters.</p>}
            </div>
            {error && (
              <p role="alert" className="text-sm text-down">
                {error}
              </p>
            )}
            <button type="submit" className="btn-primary w-full" disabled={busy || passwordTooShort}>
              {busy ? <Spinner label="Please wait" /> : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>
          <p className="text-2xs text-ink-faint">Sessions use a secure HttpOnly cookie. Passwords are hashed with Argon2id on the server.</p>
        </div>
      </Panel>
    </div>
  );
}
