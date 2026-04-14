import { useEffect, useRef, useState } from 'react';
import { API_V2_BASE } from '../config';
import type { SearchResultV2 } from '../types/v2';

const DEBOUNCE_MS = 80;

interface State {
  results: SearchResultV2[];
  loading: boolean;
}

export function useSearchV2(query: string, limit = 10): State {
  const [state, setState] = useState<State>({ results: [], loading: false });
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      abortRef.current?.abort();
      setState({ results: [], loading: false });
      return;
    }

    const timeout = setTimeout(() => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setState((prev) => ({ ...prev, loading: true }));

      fetch(
        `${API_V2_BASE}/search?q=${encodeURIComponent(trimmed)}&limit=${limit}`,
        { signal: controller.signal },
      )
        .then(async (response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const data = (await response.json()) as SearchResultV2[];
          setState({ results: data, loading: false });
        })
        .catch((err) => {
          if ((err as Error).name === 'AbortError') return;
          setState({ results: [], loading: false });
        });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timeout);
  }, [query, limit]);

  return state;
}
