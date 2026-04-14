import type { EntitiesListQuery } from '../../types/v2';
import { capabilityLabel } from '../utils/format';
import './FilterBar.css';

const CAPABILITIES = [
  'text',
  'vision',
  'audio',
  'tool_use',
  'reasoning',
  'function_calling',
  'image_generation',
  'embedding',
] as const;

const SORTS: { value: NonNullable<EntitiesListQuery['sort']>; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'input', label: 'Input $' },
  { value: 'output', label: 'Output $' },
  { value: 'context', label: 'Context' },
];

interface FilterBarProps {
  query: EntitiesListQuery;
  onChange: (next: EntitiesListQuery) => void;
  makers: string[];
  families: string[];
}

export function FilterBar({ query, onChange, makers, families }: FilterBarProps) {
  const patch = (diff: Partial<EntitiesListQuery>) => {
    onChange({ ...query, ...diff });
  };

  const toggleCapability = (cap: string) => {
    patch({ capability: query.capability === cap ? undefined : cap });
  };

  const toggleSort = (field: NonNullable<EntitiesListQuery['sort']>) => {
    if (query.sort === field) {
      patch({ order: query.order === 'asc' ? 'desc' : 'asc' });
    } else {
      patch({ sort: field, order: field === 'name' ? 'asc' : 'asc' });
    }
  };

  return (
    <div className="v2-filters">
      <div className="v2-filters-row">
        <select
          className="v2-select"
          value={query.maker ?? ''}
          onChange={(e) => patch({ maker: e.target.value || undefined })}
        >
          <option value="">All makers</option>
          {makers.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <select
          className="v2-select"
          value={query.family ?? ''}
          onChange={(e) => patch({ family: e.target.value || undefined })}
        >
          <option value="">All families</option>
          {families.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <div className="v2-filters-sort">
          {SORTS.map((s) => {
            const active = query.sort === s.value;
            const arrow = active ? (query.order === 'desc' ? '↓' : '↑') : '';
            return (
              <button
                key={s.value}
                type="button"
                className={`v2-sort-btn${active ? ' is-active' : ''}`}
                onClick={() => toggleSort(s.value)}
              >
                {s.label} <span className="v2-sort-arrow">{arrow}</span>
              </button>
            );
          })}
        </div>
      </div>
      <div className="v2-filters-row">
        <button
          type="button"
          className={`v2-chip${!query.capability ? ' is-active' : ''}`}
          onClick={() => patch({ capability: undefined })}
        >
          All
        </button>
        {CAPABILITIES.map((cap) => (
          <button
            key={cap}
            type="button"
            className={`v2-chip${query.capability === cap ? ' is-active' : ''}`}
            onClick={() => toggleCapability(cap)}
          >
            {capabilityLabel(cap)}
          </button>
        ))}
      </div>
    </div>
  );
}
