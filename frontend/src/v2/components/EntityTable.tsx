import { memo } from 'react';
import type { EntityListItemV2 } from '../../types/v2';
import {
  capabilityLabel,
  formatContext,
  formatPrice,
  makerColor,
} from '../utils/format';
import './EntityTable.css';

interface EntityTableProps {
  entities: EntityListItemV2[];
  onSelect: (slug: string) => void;
  selectedSlug: string | null;
  isInBasket: (slug: string) => boolean;
  onToggleBasket: (slug: string) => void;
}

const CAP_ORDER = [
  'text',
  'vision',
  'audio',
  'reasoning',
  'tool_use',
  'function_calling',
  'image_generation',
];

function orderedCaps(caps: string[]): string[] {
  const set = new Set(caps);
  return CAP_ORDER.filter((c) => set.has(c));
}

function Row({
  entity,
  onSelect,
  isSelected,
  inBasket,
  onToggleBasket,
}: {
  entity: EntityListItemV2;
  onSelect: (slug: string) => void;
  isSelected: boolean;
  inBasket: boolean;
  onToggleBasket: (slug: string) => void;
}) {
  const primary = entity.primary_offering;
  const pricing = primary?.pricing;
  const input = pricing?.input ?? null;
  const output = pricing?.output ?? null;
  const context = entity.context_length;
  const caps = orderedCaps(entity.capabilities);

  return (
    <div
      className={`v2-row${isSelected ? ' is-selected' : ''}${inBasket ? ' is-basket' : ''}`}
      role="button"
      tabIndex={0}
      onClick={() => onSelect(entity.slug)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(entity.slug);
        }
      }}
    >
      <div className="v2-row-main">
        <div className="v2-row-name">
          <span
            className="v2-maker-dot"
            style={{ background: makerColor(entity.maker) }}
            aria-hidden
          />
          <span className="v2-row-title">{entity.name}</span>
          {entity.is_open_source ? <span className="v2-row-oss">OSS</span> : null}
        </div>
        <div className="v2-row-maker">{entity.maker}</div>
      </div>
      <div className="v2-row-col num">{formatContext(context)}</div>
      <div className="v2-row-col num v2-row-price">{formatPrice(input)}</div>
      <div className="v2-row-col num v2-row-price">{formatPrice(output)}</div>
      <div className="v2-row-col v2-row-caps">
        {caps.slice(0, 5).map((cap) => (
          <span key={cap} className={`v2-cap v2-cap-${cap}`} title={capabilityLabel(cap)}>
            {capabilityLabel(cap)}
          </span>
        ))}
      </div>
      <div className="v2-row-col v2-row-actions">
        <button
          type="button"
          className={`v2-row-add${inBasket ? ' is-added' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleBasket(entity.slug);
          }}
          title={inBasket ? 'Remove from compare' : 'Add to compare'}
          aria-label={inBasket ? 'Remove from compare' : 'Add to compare'}
        >
          {inBasket ? '✓' : '+'}
        </button>
      </div>
    </div>
  );
}

const MemoRow = memo(Row);

function EntityTableImpl({
  entities,
  onSelect,
  selectedSlug,
  isInBasket,
  onToggleBasket,
}: EntityTableProps) {
  if (entities.length === 0) {
    return (
      <div className="v2-empty">
        <span className="v2-empty-icon">∅</span>
        <p>No models match your filters.</p>
      </div>
    );
  }

  return (
    <div className="v2-table" role="table" aria-label="Model list">
      <div className="v2-table-head" role="row">
        <div className="v2-row-main">Model</div>
        <div className="v2-row-col">Context</div>
        <div className="v2-row-col">Input / M</div>
        <div className="v2-row-col">Output / M</div>
        <div className="v2-row-col">Capabilities</div>
        <div className="v2-row-col" />
      </div>
      <div className="v2-table-body">
        {entities.map((entity) => (
          <MemoRow
            key={entity.slug}
            entity={entity}
            onSelect={onSelect}
            isSelected={entity.slug === selectedSlug}
            inBasket={isInBasket(entity.slug)}
            onToggleBasket={onToggleBasket}
          />
        ))}
      </div>
    </div>
  );
}

export const EntityTable = memo(EntityTableImpl);
