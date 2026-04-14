import { useEffect, useState } from 'react';
import { API_V2_BASE } from '../config';
import type { EntityDetailV2 } from '../types/v2';

interface State {
  detail: EntityDetailV2 | null;
  loading: boolean;
  error: string | null;
  notFound: boolean;
}

export function useEntityV2(slug: string | null | undefined): State {
  const [state, setState] = useState<State>({
    detail: null,
    loading: Boolean(slug),
    error: null,
    notFound: false,
  });

  useEffect(() => {
    if (!slug) {
      setState({ detail: null, loading: false, error: null, notFound: false });
      return;
    }

    let cancelled = false;
    setState({ detail: null, loading: true, error: null, notFound: false });

    fetch(`${API_V2_BASE}/entities/${encodeURIComponent(slug)}`)
      .then(async (response) => {
        if (cancelled) return;
        if (response.status === 404) {
          setState({ detail: null, loading: false, error: null, notFound: true });
          return;
        }
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as EntityDetailV2;
        setState({ detail: data, loading: false, error: null, notFound: false });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          detail: null,
          loading: false,
          error: err instanceof Error ? err.message : 'fetch failed',
          notFound: false,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [slug]);

  return state;
}
