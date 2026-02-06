import { useState, useEffect, useCallback } from 'react';
import type {
  ModelPricing,
  ModelUpdate,
  ProviderInfo,
  ModelFamily,
  Stats,
  Filters,
  SortConfig,
  ViewMode,
} from '../types/pricing';
import { API_BASE } from '../config';

const REQUEST_TIMEOUT_MS = 2000;
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const CACHE_SYNC_INTERVAL_MS = 60 * 1000;
const CACHE_PREFIX = 'model-price-cache:v1';

const MODELS_BASE_CACHE_KEY = `${CACHE_PREFIX}:models:base`;
const PROVIDERS_BASE_CACHE_KEY = `${CACHE_PREFIX}:providers:base`;
const FAMILIES_BASE_CACHE_KEY = `${CACHE_PREFIX}:families:base`;
const STATS_CACHE_KEY = `${CACHE_PREFIX}:stats`;
const BACKEND_REFRESH_KEY = `${CACHE_PREFIX}:backend:last_refresh`;
const DEFAULT_MODELS_QUERY = 'sort_by=model_name&sort_order=asc';

interface CacheEntry<T> {
  savedAt: number;
  data: T;
}

function buildCacheKey(scope: string, query = ''): string {
  return `${CACHE_PREFIX}:${scope}:${query}`;
}

function clearCacheNamespace(): void {
  if (typeof window === 'undefined') {
    return;
  }

  const keys: string[] = [];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key && key.startsWith(CACHE_PREFIX)) {
      keys.push(key);
    }
  }

  for (const key of keys) {
    window.localStorage.removeItem(key);
  }
}

function readBackendRefreshMarker(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.localStorage.getItem(BACKEND_REFRESH_KEY);
}

function writeBackendRefreshMarker(lastRefresh: string): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(BACKEND_REFRESH_KEY, lastRefresh);
}

function readCache<T>(key: string): T | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return null;
    }

    const entry = JSON.parse(raw) as CacheEntry<T>;
    if (!entry || typeof entry.savedAt !== 'number') {
      window.localStorage.removeItem(key);
      return null;
    }

    if (Date.now() - entry.savedAt > CACHE_TTL_MS) {
      window.localStorage.removeItem(key);
      return null;
    }

    return entry.data;
  } catch {
    return null;
  }
}

function writeCache<T>(key: string, data: T): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    const entry: CacheEntry<T> = {
      savedAt: Date.now(),
      data,
    };
    window.localStorage.setItem(key, JSON.stringify(entry));
  } catch {
    // Ignore cache write failures (e.g., storage quota or private mode).
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`Failed request (${response.status}): ${url}`);
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeoutId);
  }
}

function isDefaultModelQuery(filters: Filters, sortConfig: SortConfig): boolean {
  return (
    !filters.provider
    && !filters.capability
    && !filters.family
    && !filters.search
    && sortConfig.field === 'model_name'
    && sortConfig.order === 'asc'
  );
}

function isDefaultProvidersQuery(filters: Filters): boolean {
  return !filters.capability && !filters.family && !filters.search;
}

function isDefaultFamiliesQuery(filters: Filters): boolean {
  return !filters.provider && !filters.capability && !filters.search;
}

function applyFiltersAndSort(
  models: ModelPricing[],
  filters: Filters,
  sortConfig: SortConfig,
): ModelPricing[] {
  const searchLower = filters.search.trim().toLowerCase();

  const filtered = models.filter((model) => {
    if (filters.provider && model.provider !== filters.provider) {
      return false;
    }
    if (filters.capability && !model.capabilities.includes(filters.capability)) {
      return false;
    }
    if (filters.family && !model.model_name.toLowerCase().includes(filters.family.toLowerCase())) {
      return false;
    }
    if (searchLower && !model.model_name.toLowerCase().includes(searchLower)) {
      return false;
    }
    return true;
  });

  const order = sortConfig.order === 'desc' ? -1 : 1;
  filtered.sort((left, right) => {
    if (sortConfig.field === 'model_name') {
      return left.model_name.localeCompare(right.model_name, 'en', { sensitivity: 'base' }) * order;
    }
    if (sortConfig.field === 'input') {
      return ((left.pricing.input ?? 0) - (right.pricing.input ?? 0)) * order;
    }
    if (sortConfig.field === 'output') {
      return ((left.pricing.output ?? 0) - (right.pricing.output ?? 0)) * order;
    }
    return ((left.context_length ?? 0) - (right.context_length ?? 0)) * order;
  });

  return filtered;
}

export function useModels() {
  const [models, setModels] = useState<ModelPricing[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [families, setFamilies] = useState<ModelFamily[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  const [view, setView] = useState<ViewMode>('table');
  const [filters, setFilters] = useState<Filters>({
    provider: null,
    capability: null,
    family: null,
    search: '',
  });
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    field: 'model_name',
    order: 'asc',
  });

  const buildQueryString = useCallback(() => {
    const params = new URLSearchParams();
    if (filters.provider) params.set('provider', filters.provider);
    if (filters.capability) params.set('capability', filters.capability);
    if (filters.family) params.set('family', filters.family);
    if (filters.search) params.set('search', filters.search);
    params.set('sort_by', sortConfig.field);
    params.set('sort_order', sortConfig.order);
    return params.toString();
  }, [filters, sortConfig]);

  const buildProvidersQueryString = useCallback(() => {
    const params = new URLSearchParams();
    if (filters.capability) params.set('capability', filters.capability);
    if (filters.family) params.set('family', filters.family);
    if (filters.search) params.set('search', filters.search);
    return params.toString();
  }, [filters.capability, filters.family, filters.search]);

  const buildFamiliesQueryString = useCallback(() => {
    const params = new URLSearchParams();
    if (filters.provider) params.set('provider', filters.provider);
    if (filters.capability) params.set('capability', filters.capability);
    if (filters.search) params.set('search', filters.search);
    return params.toString();
  }, [filters.provider, filters.capability, filters.search]);

  const fetchModels = useCallback(async () => {
    const queryString = buildQueryString();
    const url = `${API_BASE}/models?${queryString}`;
    const cacheKey = buildCacheKey('models', queryString);
    const baseCached = readCache<ModelPricing[]>(MODELS_BASE_CACHE_KEY);
    const fallback = readCache<ModelPricing[]>(cacheKey)
      ?? (baseCached ? applyFiltersAndSort(baseCached, filters, sortConfig) : null);

    try {
      const data = await fetchJson<ModelPricing[]>(url);
      if (Array.isArray(data) && data.length > 0) {
        setModels(data);
        writeCache(cacheKey, data);
        if (isDefaultModelQuery(filters, sortConfig)) {
          writeCache(MODELS_BASE_CACHE_KEY, data);
        }
        setError(null);
        return;
      }

      if (fallback && fallback.length > 0) {
        setModels(fallback);
      } else {
        setModels(data);
      }
      setError(null);
    } catch (err) {
      if (fallback && fallback.length > 0) {
        setModels(fallback);
        setError(null);
        return;
      }
      setError('无法连接到后端服务，请确保后端已启动 (port 8000)');
      console.error(err);
    }
  }, [buildQueryString, filters, sortConfig]);

  const fetchProviders = useCallback(async () => {
    const queryString = buildProvidersQueryString();
    const url = queryString ? `${API_BASE}/providers?${queryString}` : `${API_BASE}/providers`;
    const cacheKey = buildCacheKey('providers', queryString);
    const fallback = readCache<ProviderInfo[]>(cacheKey)
      ?? readCache<ProviderInfo[]>(PROVIDERS_BASE_CACHE_KEY);

    try {
      const data = await fetchJson<ProviderInfo[]>(url);
      if (Array.isArray(data) && data.length > 0) {
        setProviders(data);
        writeCache(cacheKey, data);
        if (isDefaultProvidersQuery(filters)) {
          writeCache(PROVIDERS_BASE_CACHE_KEY, data);
        }
        return;
      }

      if (fallback) {
        setProviders(fallback);
      } else {
        setProviders(data);
      }
    } catch (err) {
      if (fallback) {
        setProviders(fallback);
        return;
      }
      setProviders([]);
      console.error('Failed to fetch providers:', err);
    }
  }, [buildProvidersQueryString, filters]);

  const fetchFamilies = useCallback(async () => {
    const queryString = buildFamiliesQueryString();
    const url = queryString ? `${API_BASE}/families?${queryString}` : `${API_BASE}/families`;
    const cacheKey = buildCacheKey('families', queryString);
    const fallback = readCache<ModelFamily[]>(cacheKey)
      ?? readCache<ModelFamily[]>(FAMILIES_BASE_CACHE_KEY);

    try {
      const data = await fetchJson<ModelFamily[]>(url);
      if (Array.isArray(data) && data.length > 0) {
        setFamilies(data);
        writeCache(cacheKey, data);
        if (isDefaultFamiliesQuery(filters)) {
          writeCache(FAMILIES_BASE_CACHE_KEY, data);
        }
        return;
      }

      if (fallback) {
        setFamilies(fallback);
      } else {
        setFamilies(data);
      }
    } catch (err) {
      if (fallback) {
        setFamilies(fallback);
        return;
      }
      setFamilies([]);
      console.error('Failed to fetch families:', err);
    }
  }, [buildFamiliesQueryString, filters]);

  const fetchStats = useCallback(async () => {
    const fallback = readCache<Stats>(STATS_CACHE_KEY);
    try {
      const data = await fetchJson<Stats>(`${API_BASE}/stats`);
      if (data.total_models > 0) {
        setStats(data);
        writeCache(STATS_CACHE_KEY, data);
        writeBackendRefreshMarker(data.last_refresh);
        return;
      }

      if (fallback) {
        setStats(fallback);
      } else {
        setStats(data);
      }
    } catch (err) {
      if (fallback) {
        setStats(fallback);
        return;
      }
      console.error('Failed to fetch stats:', err);
    }
  }, []);

  const syncCachesFromBackend = useCallback(async () => {
    try {
      const latestStats = await fetchJson<Stats>(`${API_BASE}/stats`);
      if (latestStats.total_models <= 0) {
        return;
      }

      const cachedRefresh = readBackendRefreshMarker();
      if (cachedRefresh === latestStats.last_refresh) {
        return;
      }

      const [baseModels, baseProviders, baseFamilies] = await Promise.all([
        fetchJson<ModelPricing[]>(`${API_BASE}/models?${DEFAULT_MODELS_QUERY}`),
        fetchJson<ProviderInfo[]>(`${API_BASE}/providers`),
        fetchJson<ModelFamily[]>(`${API_BASE}/families`),
      ]);

      if (!Array.isArray(baseModels) || baseModels.length === 0) {
        return;
      }

      clearCacheNamespace();
      writeCache(MODELS_BASE_CACHE_KEY, baseModels);
      writeCache(buildCacheKey('models', DEFAULT_MODELS_QUERY), baseModels);

      writeCache(PROVIDERS_BASE_CACHE_KEY, baseProviders);
      writeCache(buildCacheKey('providers', ''), baseProviders);

      writeCache(FAMILIES_BASE_CACHE_KEY, baseFamilies);
      writeCache(buildCacheKey('families', ''), baseFamilies);

      writeCache(STATS_CACHE_KEY, latestStats);
      writeBackendRefreshMarker(latestStats.last_refresh);

      setStats(latestStats);
      await Promise.all([fetchModels(), fetchProviders(), fetchFamilies()]);
      setError(null);
    } catch (err) {
      console.error('Failed to sync cache with backend refresh:', err);
    }
  }, [fetchModels, fetchProviders, fetchFamilies]);

  const refresh = async (provider?: string) => {
    setRefreshing(true);
    try {
      const url = provider
        ? `${API_BASE}/refresh?provider=${provider}`
        : `${API_BASE}/refresh`;
      const response = await fetch(url, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to refresh');

      await Promise.all([fetchModels(), fetchProviders(), fetchFamilies(), fetchStats()]);
    } catch (err) {
      setError('刷新失败');
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  };

  const updateModel = async (modelId: string, updates: ModelUpdate): Promise<boolean> => {
    setUpdating(modelId);
    try {
      const response = await fetch(`${API_BASE}/models/${encodeURIComponent(modelId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!response.ok) throw new Error('Failed to update model');

      const updatedModel: ModelPricing = await response.json();
      const queryString = buildQueryString();
      const cacheKey = buildCacheKey('models', queryString);
      setModels((prev) => {
        const next = prev.map((model) => (model.id === modelId ? updatedModel : model));
        writeCache(cacheKey, next);
        if (isDefaultModelQuery(filters, sortConfig)) {
          writeCache(MODELS_BASE_CACHE_KEY, next);
        }
        return next;
      });
      return true;
    } catch (err) {
      setError('更新失败');
      console.error(err);
      return false;
    } finally {
      setUpdating(null);
    }
  };

  const handleSort = (field: SortConfig['field']) => {
    setSortConfig((prev) => ({
      field,
      order: prev.field === field && prev.order === 'asc' ? 'desc' : 'asc',
    }));
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchModels(), fetchProviders(), fetchFamilies(), fetchStats()]);
      setLoading(false);
    };
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading) {
      fetchModels();
      fetchProviders();
      fetchFamilies();
    }
  }, [filters, sortConfig, fetchModels, fetchProviders, fetchFamilies, loading]);

  useEffect(() => {
    if (loading) {
      return;
    }

    void syncCachesFromBackend();
    const timerId = window.setInterval(() => {
      void syncCachesFromBackend();
    }, CACHE_SYNC_INTERVAL_MS);

    return () => {
      window.clearInterval(timerId);
    };
  }, [loading, syncCachesFromBackend]);

  const retry = useCallback(async () => {
    await Promise.all([fetchModels(), fetchProviders(), fetchFamilies(), fetchStats()]);
  }, [fetchModels, fetchProviders, fetchFamilies, fetchStats]);

  return {
    models,
    providers,
    families,
    stats,
    loading,
    refreshing,
    updating,
    error,
    view,
    setView,
    filters,
    setFilters,
    sortConfig,
    handleSort,
    refresh,
    updateModel,
    retry,
  };
}
