import { useEffect, useState, useCallback } from 'react';
import { API_V2_BASE } from '../config';
import type { EntitiesListQuery, EntityListItemV2 } from '../types/v2';

interface State {
  entities: EntityListItemV2[];
  loading: boolean;
  error: string | null;
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
  });

  const queryString = buildQueryString(query);

  const fetchEntities = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    const url = queryString
      ? `${API_V2_BASE}/entities?${queryString}`
      : `${API_V2_BASE}/entities`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as EntityListItemV2[];
      setState({ entities: data, loading: false, error: null });
    } catch (err) {
      setState({
        entities: [],
        loading: false,
        error: err instanceof Error ? err.message : 'fetch failed',
      });
    }
  }, [queryString]);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  return { ...state, refetch: fetchEntities };
}
