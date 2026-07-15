import { useEffect, useState } from 'react';
import type { EntityDetailV2 } from '../types/v2';
import { detailFromFallback, loadFallback } from '../v2/fallbackLoader';

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
      setState({
        detail: null,
        loading: false,
        error: null,
        notFound: false,
      });
      return;
    }

    let cancelled = false;
    setState({
      detail: null,
      loading: true,
      error: null,
      notFound: false,
    });

    (async () => {
      const snapshot = await loadFallback();
      if (cancelled) return;
      if (!snapshot) {
        setState({
          detail: null,
          loading: false,
          error: 'Unable to load v2-fallback.json',
          notFound: false,
        });
        return;
      }

      const detail = detailFromFallback(snapshot, slug);
      if (detail) {
        setState({
          detail,
          loading: false,
          error: null,
          notFound: false,
        });
      } else {
        setState({
          detail: null,
          loading: false,
          error: null,
          notFound: true,
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [slug]);

  return state;
}
