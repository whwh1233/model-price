import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { API_V2_BASE } from '../../config';
import type { CompareResultV2 } from '../../types/v2';
import { useCompareBasket } from '../../hooks/useCompareBasket';
import {
  capabilityLabel,
  formatContext,
  formatPrice,
  makerColor,
  providerLabel,
} from '../utils/format';
import './ComparePage.css';

export function ComparePage() {
  const { ids = '' } = useParams<{ ids: string }>();
  const [state, setState] = useState<{
    data: CompareResultV2 | null;
    loading: boolean;
    error: string | null;
  }>({ data: null, loading: true, error: null });
  const basket = useCompareBasket();
  const navigate = useNavigate();

  useEffect(() => {
    if (!ids) return;
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    fetch(`${API_V2_BASE}/compare?ids=${encodeURIComponent(ids)}`)
      .then(async (response) => {
        if (cancelled) return;
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as CompareResultV2;
        setState({ data, loading: false, error: null });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          data: null,
          loading: false,
          error: err instanceof Error ? err.message : 'fetch failed',
        });
      });
    return () => {
      cancelled = true;
    };
  }, [ids]);

  if (state.loading) return <div className="v2-loading">Loading…</div>;
  if (state.error)
    return (
      <div className="v2-error">
        <p>Failed to load comparison. {state.error}</p>
        <Link to="/" className="v2-link-accent">
          Back to home
        </Link>
      </div>
    );
  if (!state.data) return null;

  const { entities, common_capabilities, missing_ids } = state.data;

  if (entities.length === 0) {
    return (
      <div className="v2-error">
        <p>No valid models in the comparison. Try selecting some again.</p>
        <Link to="/" className="v2-link-accent">
          Back to home
        </Link>
      </div>
    );
  }

  const removeAndNav = (slug: string) => {
    basket.remove(slug);
    const remaining = entities
      .map((e) => e.entity.slug)
      .filter((s) => s !== slug);
    if (remaining.length === 0) {
      navigate('/');
    } else {
      navigate(`/compare/${remaining.join(',')}`);
    }
  };

  return (
    <div className="v2-compare">
      <header className="v2-compare-head">
        <Link to="/" className="v2-entity-back">
          ← All models
        </Link>
        <h1>Compare {entities.length} models</h1>
        {missing_ids.length > 0 ? (
          <p className="v2-compare-missing">Missing: {missing_ids.join(', ')}</p>
        ) : null}
      </header>

      <div
        className="v2-compare-grid"
        style={{ gridTemplateColumns: `160px repeat(${entities.length}, 1fr)` }}
      >
        <div className="v2-compare-label" />
        {entities.map(({ entity }) => (
          <div key={entity.slug} className="v2-compare-col-head">
            <div className="v2-compare-col-title">
              <span
                className="v2-maker-dot"
                style={{ background: makerColor(entity.maker) }}
                aria-hidden
              />
              <Link to={`/m/${entity.slug}`}>{entity.name}</Link>
              <button
                type="button"
                className="v2-compare-remove"
                onClick={() => removeAndNav(entity.slug)}
                aria-label="Remove"
                title="Remove from comparison"
              >
                ×
              </button>
            </div>
            <div className="v2-compare-col-maker">{entity.maker}</div>
          </div>
        ))}

        <Row label="Family">
          {entities.map(({ entity }) => (
            <span key={entity.slug}>{entity.family}</span>
          ))}
        </Row>
        <Row label="Context">
          {entities.map(({ entity }) => (
            <span key={entity.slug} className="num">
              {formatContext(entity.context_length)}
            </span>
          ))}
        </Row>
        <Row label="Max output">
          {entities.map(({ entity }) => (
            <span key={entity.slug} className="num">
              {formatContext(entity.max_output_tokens)}
            </span>
          ))}
        </Row>
        <Row label="Input / M">
          {entities.map(({ entity, offerings }) => {
            const p = primary(offerings, entity.primary_offering_provider);
            return (
              <span key={entity.slug} className="num v2-compare-price">
                {formatPrice(p?.pricing.input ?? null)}
              </span>
            );
          })}
        </Row>
        <Row label="Output / M">
          {entities.map(({ entity, offerings }) => {
            const p = primary(offerings, entity.primary_offering_provider);
            return (
              <span key={entity.slug} className="num v2-compare-price">
                {formatPrice(p?.pricing.output ?? null)}
              </span>
            );
          })}
        </Row>
        <Row label="Cache read">
          {entities.map(({ entity, offerings }) => {
            const p = primary(offerings, entity.primary_offering_provider);
            return (
              <span key={entity.slug} className="num v2-muted">
                {formatPrice(p?.pricing.cache_read ?? null)}
              </span>
            );
          })}
        </Row>
        <Row label="Batch input">
          {entities.map(({ entity, offerings }) => {
            const p = primary(offerings, entity.primary_offering_provider);
            return (
              <span key={entity.slug} className="num v2-muted">
                {formatPrice(p?.batch_pricing?.input ?? null)}
              </span>
            );
          })}
        </Row>
        <Row label="Primary provider">
          {entities.map(({ entity }) => (
            <span key={entity.slug}>
              {providerLabel(entity.primary_offering_provider)}
            </span>
          ))}
        </Row>
        <Row label="Capabilities">
          {entities.map(({ entity }) => (
            <div key={entity.slug} className="v2-compare-caps">
              {entity.capabilities.map((cap) => (
                <span
                  key={cap}
                  className={`v2-cap v2-cap-${cap}${
                    common_capabilities.includes(cap) ? ' is-shared' : ''
                  }`}
                >
                  {capabilityLabel(cap)}
                </span>
              ))}
            </div>
          ))}
        </Row>
      </div>

      {common_capabilities.length > 0 ? (
        <p className="v2-compare-common">
          Shared capabilities:{' '}
          {common_capabilities.map((c) => capabilityLabel(c)).join(', ')}
        </p>
      ) : null}
    </div>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <div className="v2-compare-label">{label}</div>
      {children}
    </>
  );
}

function primary(
  offerings: CompareResultV2['entities'][number]['offerings'],
  provider: string,
) {
  return offerings.find((o) => o.provider === provider) ?? offerings[0];
}
