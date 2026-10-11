'use client';

// Session state for the whole app. The session itself lives in an HttpOnly
// cookie the browser cannot read; we learn who is signed in from /api/auth/me.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, ApiError } from './api';
import type { User } from './types';

type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'unreachable';

interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');

  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
      setStatus('authenticated');
    } catch (error) {
      setUser(null);
      setStatus(error instanceof ApiError && error.status === 401 ? 'anonymous' : 'unreachable');
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const session = await api.login(email, password);
    setUser(session.user);
    setStatus('authenticated');
  }, []);

  const signup = useCallback(async (email: string, password: string, displayName?: string) => {
    const session = await api.signup(email, password, displayName);
    setUser(session.user);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      setStatus('anonymous');
    }
  }, []);

  const value = useMemo(
    () => ({ user, status, refresh, login, signup, logout }),
    [user, status, refresh, login, signup, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
