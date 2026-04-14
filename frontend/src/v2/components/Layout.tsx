import { Link, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { CompareBasket } from './CompareBasket';
import { ThemeToggle } from './ThemeToggle';
import { LocaleToggle } from './LocaleToggle';
import { useI18n } from '../i18n/localeContext';
import './Layout.css';

interface LayoutProps {
  children: ReactNode;
  onOpenPalette: () => void;
}

export function Layout({ children, onOpenPalette }: LayoutProps) {
  const location = useLocation();
  const { t } = useI18n();
  const isHome = location.pathname === '/';

  return (
    <div className="v2-shell">
      <header className="v2-topbar">
        <Link to="/" className="v2-brand">
          <span className="v2-brand-mark">⬡</span>
          <span className="v2-brand-name">Model Price</span>
          <span className="v2-brand-tag">{t('brand.tagline')}</span>
        </Link>
        <div className="v2-topbar-right">
          {!isHome && (
            <button
              type="button"
              className="v2-topbar-search"
              onClick={onOpenPalette}
              aria-label={t('nav.open_palette')}
            >
              <span className="v2-topbar-search-icon">⌕</span>
              <span className="v2-topbar-search-label">
                {t('nav.search_placeholder')}
              </span>
              <kbd>⌘K</kbd>
            </button>
          )}
          <LocaleToggle />
          <ThemeToggle />
        </div>
      </header>

      <main className="v2-main">{children}</main>

      <footer className="v2-footer">
        <span>{t('footer.tagline')}</span>
        <span className="v2-footer-sep">·</span>
        <span>{t('footer.unit')}</span>
        <span className="v2-footer-sep">·</span>
        <a href="https://github.com/xiaobox/model-price" target="_blank" rel="noreferrer">
          {t('footer.github')}
        </a>
      </footer>

      <CompareBasket />
    </div>
  );
}
