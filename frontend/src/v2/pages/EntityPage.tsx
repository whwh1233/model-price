import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useEntityV2 } from '../../hooks/useEntityV2';
import { useCompareBasket } from '../compareBasketContext';
import { AlternativesList } from '../components/AlternativesList';
import {
  capabilityLabel,
  formatContext,
  formatPrice,
  makerColor,
  providerLabel,
} from '../utils/format';
import { LITELLM_REGISTRY_URL, officialLinkForMaker } from '../utils/officialLinks';
import './EntityPage.css';

export function EntityPage() {
  const { slug } = useParams<{ slug: string }>();
  const { detail, loading, notFound } = useEntityV2(slug);
  const basket = useCompareBasket();
  const navigate = useNavigate();
  // All hooks must run unconditionally — early returns come AFTER.
  const [copied, setCopied] = useState(false);

  if (loading) return <div className="v2-loading">Loading…</div>;
  if (notFound) {
    return (
      <div className="v2-error">
        <p>
          Model "{slug}" not found.{' '}
          <Link to="/" className="v2-link-accent">
            Back to home
          </Link>
        </p>
      </div>
    );
  }
  if (!detail) return null;

  const { entity, offerings, alternatives } = detail;
  const inBasket = basket.has(entity.slug);
  const primary = offerings.find((o) => o.provider === entity.primary_offering_provider);

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
    <article className="v2-entity-page">
      <Link to="/" className="v2-entity-back">
        ← All models
      </Link>

      <header className="v2-entity-head">
        <div className="v2-entity-title">
          <span
            className="v2-maker-dot v2-entity-dot"
            style={{ background: makerColor(entity.maker) }}
            aria-hidden
          />
          <h1>{entity.name}</h1>
          {entity.is_open_source ? <span className="v2-row-oss">OSS</span> : null}
        </div>
        <p className="v2-entity-meta">
          {entity.maker} · {entity.family} · {formatContext(entity.context_length)}{' '}
          context
          {entity.max_output_tokens ? (
            <> · {formatContext(entity.max_output_tokens)} max output</>
          ) : null}
        </p>

        <div className="v2-entity-actions">
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
            onClick={() => basket.toggle(entity.slug)}
          >
            {inBasket ? '✓ In compare' : '+ Add to compare'}
          </button>
        </div>

        <OfficialLinksStrip maker={entity.maker} />
      </header>

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
            onNavigate={(s) => navigate(`/m/${s}`)}
          />
        </section>
      ) : null}
    </article>
  );
}

function OfficialLinksStrip({ maker }: { maker: string }) {
  const link = officialLinkForMaker(maker);
  return (
    <div className="v2-official-links">
      <span className="v2-official-label">For full details:</span>
      {link ? (
        <>
          <a href={link.pricing} target="_blank" rel="noreferrer" className="v2-official-link">
            {maker} pricing ↗
          </a>
          {link.docs ? (
            <a href={link.docs} target="_blank" rel="noreferrer" className="v2-official-link">
              {maker} docs ↗
            </a>
          ) : null}
        </>
      ) : null}
      <a
        href={LITELLM_REGISTRY_URL}
        target="_blank"
        rel="noreferrer"
        className="v2-official-link v2-official-link-muted"
      >
        source: LiteLLM ↗
      </a>
    </div>
  );
}
