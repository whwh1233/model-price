import type { ReactNode } from 'react';
import { CompareBasket } from './CompareBasket';
import './Layout.css';

interface LayoutProps {
  children: ReactNode;
  onOpenPalette: () => void;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="v2-shell">
      <main className="v2-main">{children}</main>

      <CompareBasket />
    </div>
  );
}
