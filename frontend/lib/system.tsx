'use client';

// Backend capabilities (data mode, research mode, embedding readiness),
// loaded once and shared. While the embedding model is downloading, the
// status is re-polled every few seconds so upload/search unlock on their own.

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api } from './api';
import type { EmbeddingsStatus, SystemStatus } from './types';

interface SystemContextValue {
  status: SystemStatus | null;
  reachable: boolean | null;
  reload: () => void;
}

const SystemContext = createContext<SystemContextValue>({ status: null, reachable: null, reload: () => {} });
const POLL_MS = 5_000;

/** Accept the older string form ("onnx") as well as the current object. */
export function normalizeEmbeddings(value: unknown): EmbeddingsStatus {
  if (value && typeof value === 'object') return value as EmbeddingsStatus;
  return { provider: String(value ?? 'unknown'), ready: true, status: 'ready', downloaded_mb: null, total_mb: null, note: null };
}

export function SystemProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const load = useCallback(() => {
    api
      .status()
      .then((s) => {
        setStatus({ ...s, embeddings: normalizeEmbeddings(s.embeddings) });
        setReachable(true);
      })
      .catch(() => {
        setStatus(null);
        setReachable(false);
      });
  }, []);
  useEffect(load, [load]);

  const downloading = status?.embeddings.status === 'downloading' || status?.embeddings.status === 'not_started';
  useEffect(() => {
    if (!downloading) return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [downloading, load]);

  return <SystemContext.Provider value={{ status, reachable, reload: load }}>{children}</SystemContext.Provider>;
}

export const useSystem = () => useContext(SystemContext);
