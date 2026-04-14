import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useEntityV2 } from '../../hooks/useEntityV2';
import { AlternativesList } from './AlternativesList';
import {
  capabilityLabel,
  formatContext,
  formatPrice,
  makerColor,
  providerLabel,
} from '../utils/format';
import './EntityDrawer.css';

interface EntityDrawerProps {
  slug: string | null;
  onClose: () => void;
  onToggleBasket: (slug: string) => void;
  isInBasket: (slug: string) => boolean;
  onNavigateSlug: (slug: string) => void;
}

export function EntityDrawer({
  slug,
  onClose,
  onToggleBasket,
  isInBasket,
  onNavigateSlug,
}: EntityDrawerProps) {
  const { detail, loading, notFound } = useEntityV2(slug);

  useEffect(() => {
    if (!slug) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [slug, onClose]);

  if (!slug) return null;

  return (
    <>
      <div className="v2-drawer-scrim" onClick={onClose} />
      <aside className="v2-drawer" role="dialog" aria-label="Model detail">
        <header className="v2-drawer-head">
          <button
            type="button"
            className="v2-drawer-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
          <Link
            to={`/m/${slug}`}
            className="v2-drawer-expand"
            title="Open full page"
          >
            Open full page ↗
          </Link>
        </header>

        {loading ? (
          <div className="v2-drawer-loading">Loading…</div>
        ) : notFound ? (
          <div className="v2-drawer-empty">Model "{slug}" not found.</div>
        ) : detail ? (
          <DrawerContent
            detail={detail}
            onToggleBasket={onToggleBasket}
            isInBasket={isInBasket}
            onNavigateSlug={onNavigateSlug}
          />
        ) : null}
      </aside>
    </>
  );
}

function DrawerContent({
  detail,
  onToggleBasket,
  isInBasket,
  onNavigateSlug,
}: {
  detail: ReturnType<typeof useEntityV2>['detail'] extends infer T
    ? NonNullable<T>
    : never;
  onToggleBasket: (slug: string) => void;
  isInBasket: (slug: string) => boolean;
  onNavigateSlug: (slug: string) => void;
}) {
  const { entity, offerings, alternatives } = detail;
  const inBasket = isInBasket(entity.slug);
  const primary = offerings.find((o) => o.provider === entity.primary_offering_provider)
    ?? offerings[0];
  const [copied, setCopied] = useState(false);

  const copyModelId = async () => {
    if (!primary) return;
    try {
      await navigator.clipboard.writeText(primary.provider_model_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  return (
    <div className="v2-drawer-body">
      <div className="v2-drawer-title">
        <span
          className="v2-maker-dot"
          style={{ background: makerColor(entity.maker) }}
          aria-hidden
        />
        <h2>{entity.name}</h2>
        {entity.is_open_source ? <span className="v2-row-oss">OSS</span> : null}
      </div>
      <div className="v2-drawer-meta">
        <span>{entity.maker}</span>
        <span className="v2-drawer-sep">·</span>
        <span>{entity.family}</span>
        <span className="v2-drawer-sep">·</span>
        <span>{formatContext(entity.context_length)} context</span>
        {entity.max_output_tokens ? (
          <>
            <span className="v2-drawer-sep">·</span>
            <span>{formatContext(entity.max_output_tokens)} max output</span>
          </>
        ) : null}
      </div>

      <div className="v2-drawer-actions">
        <button
          type="button"
          className={`v2-btn v2-btn-primary${copied ? ' is-copied' : ''}`}
          onClick={copyModelId}
          disabled={!primary}
        >
          {copied ? '✓ Copied!' : 'Copy model_id'}
          <span className="v2-btn-sub mono">
            {primary?.provider_model_id ?? ''}
          </span>
        </button>
        <button
          type="button"
          className={`v2-btn${inBasket ? ' is-active' : ''}`}
          onClick={() => onToggleBasket(entity.slug)}
        >
          {inBasket ? '✓ In compare' : '+ Add to compare'}
        </button>
      </div>

      <section className="v2-drawer-section">
        <h3>Capabilities</h3>
        <div className="v2-caps-grid">
          {entity.capabilities.map((cap) => (
            <span key={cap} className={`v2-cap v2-cap-${cap}`}>
              {capabilityLabel(cap)}
            </span>
          ))}
        </div>
        <div className="v2-drawer-modality">
          <div>
            <span className="v2-drawer-label">Input</span>
            <span>{entity.input_modalities.join(', ')}</span>
          </div>
          <div>
            <span className="v2-drawer-label">Output</span>
            <span>{entity.output_modalities.join(', ')}</span>
          </div>
        </div>
      </section>

      <section className="v2-drawer-section">
        <h3>Pricing across providers</h3>
        <div className="v2-offerings">
          <div className="v2-offer-head">
            <span>Provider</span>
            <span>Input</span>
            <span>Output</span>
            <span>Cache read</span>
            <span>Batch in</span>
          </div>
          {offerings.map((o) => {
            const isPrimary = o.provider === entity.primary_offering_provider;
            return (
              <div
                key={`${o.provider}-${o.provider_model_id}`}
                className={`v2-offer${isPrimary ? ' is-primary' : ''}`}
              >
                <div className="v2-offer-provider">
                  <span>{providerLabel(o.provider)}</span>
                  {isPrimary ? <span className="v2-offer-tag">primary</span> : null}
                  {o.notes ? (
                    <span className="v2-offer-note" title={o.notes}>
                      ⓘ
                    </span>
                  ) : null}
                </div>
                <span className="num">{formatPrice(o.pricing.input)}</span>
                <span className="num">{formatPrice(o.pricing.output)}</span>
                <span className="num v2-muted">{formatPrice(o.pricing.cache_read)}</span>
                <span className="num v2-muted">
                  {formatPrice(o.batch_pricing?.input ?? null)}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {alternatives.length > 0 ? (
        <section className="v2-drawer-section">
          <h3>Same tier, cheaper</h3>
          <AlternativesList
            alternatives={alternatives}
            onNavigate={onNavigateSlug}
          />
        </section>
      ) : null}
    </div>
  );
}
