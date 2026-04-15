import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { ReactNode } from 'react';

export type ThemeMode = 'dark' | 'light' | 'system';
type ResolvedTheme = 'dark' | 'light';

const STORAGE_KEY = 'model-price-v2:theme';

interface ThemeValue {
  mode: ThemeMode;
  resolved: ResolvedTheme;
  setMode: (next: ThemeMode) => void;
  cycle: () => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

function readInitial(): ThemeMode {
  if (typeof window === 'undefined') return 'dark';
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === 'dark' || raw === 'light' || raw === 'system') return raw;
  } catch {
    // ignore
  }
  return 'light';
}

function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === 'dark' || mode === 'light') return mode;
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readInitial);
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(readInitial()));

  // Persist + re-resolve whenever the user picks a mode.
  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const cycle = useCallback(() => {
    setMode(mode === 'dark' ? 'light' : mode === 'light' ? 'system' : 'dark');
  }, [mode, setMode]);

  // Keep `resolved` in sync with either explicit mode or the OS setting.
  useEffect(() => {
    setResolved(resolveTheme(mode));
    if (mode !== 'system') return;
    const media = window.matchMedia('(prefers-color-scheme: light)');
    const handler = () => setResolved(media.matches ? 'light' : 'dark');
    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
  }, [mode]);

  // Reflect to <html data-theme="…"> so CSS custom properties switch.
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', resolved);
  }, [resolved]);

  return (
    <ThemeContext.Provider value={{ mode, resolved, setMode, cycle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return ctx;
}
