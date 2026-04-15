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
      <main className="v2-main">{children}</main>

      <CompareBasket />
    </div>
  );
}
