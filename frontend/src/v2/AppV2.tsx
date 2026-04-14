import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { CommandPalette } from './components/CommandPalette';
import { HomePage } from './pages/HomePage';
import { EntityPage } from './pages/EntityPage';
import { ComparePage } from './pages/ComparePage';

import '../styles/tokens.css';

export function AppV2() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      } else if (e.key === '/' && !paletteOpen) {
        const target = e.target as HTMLElement | null;
        const tag = target?.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA' && target?.isContentEditable !== true) {
          e.preventDefault();
          setPaletteOpen(true);
        }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [paletteOpen]);

  return (
    <>
      <Layout onOpenPalette={() => setPaletteOpen(true)}>
        <Routes>
          <Route path="/" element={<HomePage onOpenPalette={() => setPaletteOpen(true)} />} />
          <Route path="/m/:slug" element={<EntityPage />} />
          <Route path="/compare/:ids" element={<ComparePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </>
  );
}
