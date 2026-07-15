// Client-side v2 snapshot loader.
//
// The snapshot is a 100KB-ish gzipped JSON shipped in the Vite
// bundle (generated at build time from backend/data/v2/*.json).
// The UI reads this snapshot directly; the backend is only used as
// an offline refresh tool when regenerating the bundled data.

import type {
  AlternativeV2,
  CompareResultV2,
  EntitiesListQuery,
  EntityCoreV2,
  EntityDetailV2,
  EntityListItemV2,
  OfferingV2,
  SearchResultV2,
} from '../types/v2';

interface V2Snapshot {
  version: string;
  generated_at: string;
  entity_count: number;
  source_last_refresh: string | null;
  entities: EntityCoreV2[];
  offerings_by_entity: Record<string, OfferingV2[]>;
  alternatives_by_entity: Record<string, AlternativeV2[]>;
}

const FALLBACK_URL = '/v2-fallback.json';

const VISIBLE_MODEL_SLUGS = new Set([
  // Existing curated public set.
  'claude-sonnet-4-6',
  'claude-opus-4-6',
  'claude-opus-4-7',
  'claude-haiku-4-5',
  'gpt-5-4',
  'gpt-5-5',
  'gpt-5-3-codex',

  // GPT-5.6: keep only the three OpenRouter variants that have sane prices.
  'gpt-5-6-luna',
  'gpt-5-6-sol',
  'gpt-5-6-terra',

  // Newly added Claude models from the latest snapshot.
  'claude-fable-5',
  'claude-mythos-5',
  'claude-opus-4-8',
  'claude-sonnet-5',
]);

let cached: V2Snapshot | null = null;
let loading: Promise<V2Snapshot | null> | null = null;

export async function loadFallback(): Promise<V2Snapshot | null> {
  if (cached) return cached;
  if (loading) return loading;
  loading = (async () => {
    try {
      const response = await fetch(FALLBACK_URL);
      if (!response.ok) return null;
      const data = (await response.json()) as V2Snapshot;
      cached = data;
      return data;
    } catch {
      return null;
    } finally {
      loading = null;
    }
  })();
  return loading;
}

export function resetFallbackCacheForTests(): void {
  cached = null;
  loading = null;
}

// ─── Primary offering helper ────────────────────────────────

function primaryOffering(
  entity: EntityCoreV2,
  offerings: OfferingV2[] | undefined,
): OfferingV2 | null {
  if (!offerings || offerings.length === 0) return null;
  return (
    offerings.find((o) => o.provider === entity.primary_offering_provider) ??
    offerings[0]
  );
}

function toListItem(
  entity: EntityCoreV2,
  offs: OfferingV2[] | undefined,
): EntityListItemV2 {
  return {
    ...entity,
    primary_offering: primaryOffering(entity, offs),
  };
}

function isVisible(slug: string): boolean {
  return VISIBLE_MODEL_SLUGS.has(slug);
}

// ─── Snapshot query helpers ─────────────────────────────────

export function listFromFallback(
  snapshot: V2Snapshot,
  query: EntitiesListQuery,
): EntityListItemV2[] {
  let list = snapshot.entities.filter((entity) => isVisible(entity.slug));

  if (query.q) {
    const ql = query.q.toLowerCase();
    list = list.filter(
      (e) =>
        (e.name ?? '').toLowerCase().includes(ql) ||
        (e.canonical_id ?? '').toLowerCase().includes(ql) ||
        (e.family ?? '').toLowerCase().includes(ql),
    );
  }
  if (query.family) list = list.filter((e) => e.family === query.family);
  if (query.maker) list = list.filter((e) => e.maker === query.maker);
  if (query.capability) {
    list = list.filter((e) => (e.capabilities ?? []).includes(query.capability!));
  }
  if (query.min_context != null) {
    list = list.filter(
      (e) => (e.context_length ?? 0) >= query.min_context!,
    );
  }

  let items = list.map((e) => toListItem(e, snapshot.offerings_by_entity[e.slug]));

  if (query.max_input_price != null) {
    items = items.filter((item) => {
      const price = item.primary_offering?.pricing?.input;
      return price != null && price <= query.max_input_price!;
    });
  }

  const sort = query.sort ?? 'name';
  const reverse = query.order === 'desc';
  const getPrice = (item: EntityListItemV2, field: 'input' | 'output'): number => {
    const value = item.primary_offering?.pricing?.[field];
    return value != null ? value : Infinity;
  };
  const sorter = (a: EntityListItemV2, b: EntityListItemV2): number => {
    let d = 0;
    if (sort === 'input') d = getPrice(a, 'input') - getPrice(b, 'input');
    else if (sort === 'output') d = getPrice(a, 'output') - getPrice(b, 'output');
    else if (sort === 'context')
      d = (a.context_length ?? 0) - (b.context_length ?? 0);
    else d = (a.name ?? '').toLowerCase().localeCompare((b.name ?? '').toLowerCase());
    return reverse ? -d : d;
  };
  return [...items].sort(sorter);
}

export function detailFromFallback(
  snapshot: V2Snapshot,
  slug: string,
): EntityDetailV2 | null {
  const entity = snapshot.entities.find((e) => e.slug === slug);
  if (!entity || !isVisible(entity.slug)) return null;
  return {
    entity,
    offerings: snapshot.offerings_by_entity[slug] ?? [],
    alternatives: (snapshot.alternatives_by_entity[slug] ?? []).filter((alt) =>
      isVisible(alt.canonical_id),
    ),
  };
}

export function compareFromFallback(
  snapshot: V2Snapshot,
  ids: string[],
): CompareResultV2 {
  const requested = ids.map((s) => s.trim()).filter(Boolean);
  const entities: EntityDetailV2[] = [];
  const missing: string[] = [];
  const capSets: Array<Set<string>> = [];

  for (const slug of requested) {
    const detail = detailFromFallback(snapshot, slug);
    if (!detail) {
      missing.push(slug);
      continue;
    }
    entities.push(detail);
    capSets.push(new Set(detail.entity.capabilities ?? []));
  }

  const common =
    capSets.length > 0
      ? [...capSets.reduce((acc, set) => {
          return new Set([...acc].filter((cap) => set.has(cap)));
        })].sort()
      : [];

  return {
    entities,
    common_capabilities: common,
    requested_ids: requested,
    missing_ids: missing,
  };
}

export function searchFallback(
  snapshot: V2Snapshot,
  query: string,
  limit = 10,
): SearchResultV2[] {
  const ql = query.toLowerCase().trim();
  if (!ql) return [];
  const scored: Array<[number, SearchResultV2]> = [];
  for (const entity of snapshot.entities.filter((item) => isVisible(item.slug))) {
    const name = (entity.name ?? '').toLowerCase();
    const canon = (entity.canonical_id ?? '').toLowerCase();
    const family = (entity.family ?? '').toLowerCase();
    let rank: number;
    if (name === ql || canon === ql) rank = 0;
    else if (name.startsWith(ql) || canon.startsWith(ql)) rank = 1;
    else if (name.includes(ql) || canon.includes(ql)) rank = 2;
    else if (family.includes(ql)) rank = 3;
    else continue;
    const primary = primaryOffering(
      entity,
      snapshot.offerings_by_entity[entity.slug],
    );
    scored.push([
      rank,
      {
        canonical_id: entity.canonical_id,
        slug: entity.slug,
        name: entity.name,
        family: entity.family ?? null,
        maker: entity.maker ?? null,
        primary_input_price: primary?.pricing?.input ?? null,
        primary_output_price: primary?.pricing?.output ?? null,
      },
    ]);
  }
  scored.sort((a, b) => {
    if (a[0] !== b[0]) return a[0] - b[0];
    return a[1].name.toLowerCase().localeCompare(b[1].name.toLowerCase());
  });
  return scored.slice(0, limit).map((pair) => pair[1]);
}
