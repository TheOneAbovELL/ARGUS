'use client';

// Tiny data-loading hook: tracks loading/error/data for one async call and
// ignores results from superseded calls, so a slow old response can never
// overwrite a newer one.

import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  reload: () => void;
  setData: (value: T | null) => void;
}

export function useAsync<T>(fn: (() => Promise<T>) | null, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState<boolean>(fn !== null);
  const [nonce, setNonce] = useState(0);
  const callId = useRef(0);

  useEffect(() => {
    const id = ++callId.current;
    if (!fn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fn()
      .then((value) => {
        if (id === callId.current) setData(value);
      })
      .catch((err) => {
        if (id === callId.current) {
          setError(err);
          setData(null);
        }
      })
      .finally(() => {
        if (id === callId.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload, setData };
}
