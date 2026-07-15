import { useCallback, useEffect, useState } from 'react';
import type { EntitiesListQuery, EntityListItemV2 } from '../types/v2';
import { listFromFallback, loadFallback } from '../v2/fallbackLoader';

interface State {
  entities: EntityListItemV2[];
  loading: boolean;
  error: string | null;
}

export function useEntitiesV2(query: EntitiesListQuery): State & {
  refetch: () => Promise<void>;
} {
  const [state, setState] = useState<State>({
    entities: [],
    loading: true,
    error: null,
  });

  const queryKey = JSON.stringify(query);

  const fetchEntities = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    const snapshot = await loadFallback();
    if (!snapshot) {
      setState({
        entities: [],
        loading: false,
        error: 'Unable to load v2-fallback.json',
      });
      return;
    }
    setState({
      entities: listFromFallback(snapshot, query),
      loading: false,
      error: null,
    });
    // queryKey is the serialized cache key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey]);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  return { ...state, refetch: fetchEntities };
}
