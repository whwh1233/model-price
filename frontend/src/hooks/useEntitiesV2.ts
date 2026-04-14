import { useCallback, useEffect, useState } from 'react';
import { API_V2_BASE } from '../config';
import type { EntitiesListQuery, EntityListItemV2 } from '../types/v2';
import { listFromFallback, loadFallback } from '../v2/fallbackLoader';

const BACKEND_TIMEOUT_MS = 15000;

interface State {
  entities: EntityListItemV2[];
  loading: boolean;
  error: string | null;
  fromFallback: boolean;
}

function buildQueryString(query: EntitiesListQuery): string {
  const params = new URLSearchParams();
  if (query.q) params.set('q', query.q);
  if (query.family) params.set('family', query.family);
  if (query.maker) params.set('maker', query.maker);
  if (query.capability) params.set('capability', query.capability);
  if (typeof query.min_context === 'number') {
    params.set('min_context', String(query.min_context));
  }
  if (typeof query.max_input_price === 'number') {
    params.set('max_input_price', String(query.max_input_price));
  }
  if (query.sort) params.set('sort', query.sort);
  if (query.order) params.set('order', query.order);
  return params.toString();
}

export function useEntitiesV2(query: EntitiesListQuery): State & {
  refetch: () => Promise<void>;
} {
  const [state, setState] = useState<State>({
    entities: [],
    loading: true,
    error: null,
    fromFallback: false,
  });

  const queryString = buildQueryString(query);

  const fetchEntities = useCallback(async () => {
    // Stage 1: paint from the local snapshot instantly. During a cold
    // Render free-tier boot this is what the user actually sees for
    // the first 30-60 seconds, and it's interactive the whole time.
    const snapshot = await loadFallback();
    let paintedFallback = false;
    if (snapshot) {
      const fallbackList = listFromFallback(snapshot, query);
      setState({
        entities: fallbackList,
        loading: true,
        error: null,
        fromFallback: true,
      });
      paintedFallback = true;
    } else {
      setState((prev) => ({ ...prev, loading: true, error: null }));
    }

    // Stage 2: fire the real backend request and swap in live data
    // when it arrives. If it times out or errors, keep the fallback
    // visible and swallow the error — the user still has content.
    const url = queryString
      ? `${API_V2_BASE}/entities?${queryString}`
      : `${API_V2_BASE}/entities`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as EntityListItemV2[];
      setState({
        entities: data,
        loading: false,
        error: null,
        fromFallback: false,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: paintedFallback
          ? null
          : err instanceof Error
            ? err.message
            : 'fetch failed',
      }));
    } finally {
      clearTimeout(timeout);
    }
    // queryString is the serialized cache key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  return { ...state, refetch: fetchEntities };
}
