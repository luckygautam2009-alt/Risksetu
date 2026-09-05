/**
 * Hook that fetches LIVE_RISK_V1 for given coordinates.
 * Returns loading / error / data states.
 * Only fires when coordinates change AND are valid.
 */
import { useEffect, useRef, useState } from 'react';
import { fetchLiveRisk, type LiveRiskResponse } from '../services/api';

export type FetchState = 'idle' | 'loading' | 'success' | 'error' | 'unavailable';

export interface LiveRiskState {
  state: FetchState;
  data: LiveRiskResponse['data'] | null;
  error: string | null;
}

export function useLiveRisk(lat: number | null, lon: number | null): LiveRiskState {
  const [result, setResult] = useState<LiveRiskState>({ state: 'idle', data: null, error: null });
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (lat === null || lon === null) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setResult({ state: 'loading', data: null, error: null });

    fetchLiveRisk(lat, lon)
      .then((res) => {
        if (controller.signal.aborted) return;
        setResult({ state: 'success', data: res.data, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const msg = err instanceof Error ? err.message : 'Failed to fetch live risk.';
        setResult({ state: 'error', data: null, error: msg });
      });

    return () => controller.abort();
  }, [lat, lon]);

  return result;
}
