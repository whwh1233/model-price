import { useEffect, useRef, useState } from 'react';
import type { SearchResultV2 } from '../types/v2';
import { loadFallback, searchFallback } from '../v2/fallbackLoader';

const DEBOUNCE_MS = 80;

interface State {
  results: SearchResultV2[];
  loading: boolean;
}

/**
 * Cmd+K search runs entirely client-side against the v2 fallback
 * snapshot. At ~650 entities substring matching is sub-millisecond
 * per keystroke, and it avoids a network round-trip — which matters
 * most when the Render free-tier backend is cold. The backend
 * /api/v2/search endpoint remains part of the public contract for
 * API consumers, but the UI no longer calls it.
 */
export function useSearchV2(query: string, limit = 10): State {
  const [state, setState] = useState<State>({ results: [], loading: false });
  const tokenRef = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setState({ results: [], loading: false });
      return;
    }

    const token = ++tokenRef.current;
    setState((prev) => ({ ...prev, loading: true }));

    const timeout = setTimeout(async () => {
      const snapshot = await loadFallback();
      if (tokenRef.current !== token) return;
      if (!snapshot) {
        setState({ results: [], loading: false });
        return;
      }
      const results = searchFallback(snapshot, trimmed, limit);
      setState({ results, loading: false });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timeout);
  }, [query, limit]);

  return state;
}
