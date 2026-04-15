import type { EntityListItemV2 } from '../../types/v2';

const COLUMNS: Array<{ header: string; value: (e: EntityListItemV2) => unknown }> = [
  { header: 'slug', value: (e) => e.slug },
  { header: 'name', value: (e) => e.name },
  { header: 'maker', value: (e) => e.maker },
  { header: 'family', value: (e) => e.family },
  { header: 'primary_provider', value: (e) => e.primary_offering_provider },
  { header: 'provider_model_id', value: (e) => e.primary_offering?.provider_model_id ?? '' },
  { header: 'context_length', value: (e) => e.context_length },
  { header: 'max_output_tokens', value: (e) => e.max_output_tokens },
  { header: 'input_usd_per_mtok', value: (e) => e.primary_offering?.pricing.input ?? null },
  { header: 'output_usd_per_mtok', value: (e) => e.primary_offering?.pricing.output ?? null },
  { header: 'cache_read_usd_per_mtok', value: (e) => e.primary_offering?.pricing.cache_read ?? null },
  { header: 'cache_write_usd_per_mtok', value: (e) => e.primary_offering?.pricing.cache_write ?? null },
  { header: 'image_input_usd_per_mtok', value: (e) => e.primary_offering?.pricing.image_input ?? null },
  { header: 'audio_input_usd_per_mtok', value: (e) => e.primary_offering?.pricing.audio_input ?? null },
  { header: 'audio_output_usd_per_mtok', value: (e) => e.primary_offering?.pricing.audio_output ?? null },
  { header: 'embedding_usd_per_mtok', value: (e) => e.primary_offering?.pricing.embedding ?? null },
  { header: 'batch_input_usd_per_mtok', value: (e) => e.primary_offering?.batch_pricing?.input ?? null },
  { header: 'batch_output_usd_per_mtok', value: (e) => e.primary_offering?.batch_pricing?.output ?? null },
  { header: 'capabilities', value: (e) => e.capabilities.join(' | ') },
  { header: 'input_modalities', value: (e) => e.input_modalities.join(' | ') },
  { header: 'output_modalities', value: (e) => e.output_modalities.join(' | ') },
  { header: 'is_open_source', value: (e) => (e.is_open_source == null ? '' : e.is_open_source ? 'true' : 'false') },
  { header: 'last_refreshed', value: (e) => e.last_refreshed },
];

function escapeCell(value: unknown): string {
  if (value == null) return '';
  const str = String(value);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function buildEntitiesCsv(entities: EntityListItemV2[]): string {
  const lines: string[] = [];
  lines.push(COLUMNS.map((col) => escapeCell(col.header)).join(','));
  for (const entity of entities) {
    lines.push(COLUMNS.map((col) => escapeCell(col.value(entity))).join(','));
  }
  return lines.join('\r\n');
}

function formatDateStamp(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`;
}

export function exportEntitiesToCsv(entities: EntityListItemV2[]): void {
  const csv = buildEntitiesCsv(entities);
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `model-price-${formatDateStamp(new Date())}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
