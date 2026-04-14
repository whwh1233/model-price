import { Link, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { CompareBasket } from './CompareBasket';
import './Layout.css';

interface LayoutProps {
  children: ReactNode;
  onOpenPalette: () => void;
}

export function Layout({ children, onOpenPalette }: LayoutProps) {
  const location = useLocation();
  // Home page has its own hero search; a second topbar input would be
  // redundant. Detail / compare routes lose the hero, so show it there.
  const showTopbarSearch = location.pathname !== '/';

  return (
    <div className="v2-shell">
      <header className="v2-topbar">
        <Link to="/" className="v2-brand">
          <span className="v2-brand-mark">⬡</span>
          <span className="v2-brand-name">Model Price</span>
          <span className="v2-brand-tag">v2 preview</span>
        </Link>
        {showTopbarSearch ? (
          <button
            type="button"
            className="v2-topbar-search"
            onClick={onOpenPalette}
            aria-label="Open command palette"
          >
            <span className="v2-topbar-search-icon">⌕</span>
            <span className="v2-topbar-search-label">Search models…</span>
            <kbd>⌘K</kbd>
          </button>
        ) : (
          <button
            type="button"
            className="v2-topbar-palette-mini"
            onClick={onOpenPalette}
            aria-label="Open command palette"
            title="Quick search (⌘K)"
          >
            <kbd>⌘K</kbd>
          </button>
        )}
      </header>

      <main className="v2-main">{children}</main>

      <footer className="v2-footer">
        <span>Model Price · compare 600+ LLMs from 6 providers</span>
        <span className="v2-footer-sep">·</span>
        <span>Prices per 1M tokens</span>
        <span className="v2-footer-sep">·</span>
        <a href="https://github.com/xiaobox/model-price" target="_blank" rel="noreferrer">
          GitHub
        </a>
      </footer>

      <CompareBasket />
    </div>
  );
}
