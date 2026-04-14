import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearchV2 } from '../../hooks/useSearchV2';
import { useCompareBasket } from '../../hooks/useCompareBasket';
import { formatPrice, makerColor } from '../utils/format';
import './CommandPalette.css';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();
  const basket = useCompareBasket();
  const { results } = useSearchV2(query, 12);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setCursor(0);
    const raf = requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
    return () => cancelAnimationFrame(raf);
  }, [open]);

  useEffect(() => {
    setCursor(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (!results.length) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setCursor((c) => (c + 1) % results.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setCursor((c) => (c - 1 + results.length) % results.length);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const pick = results[cursor];
        if (pick) {
          navigate(`/m/${pick.slug}`);
          onClose();
        }
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'c') {
        e.preventDefault();
        const pick = results[cursor];
        if (pick) {
          navigator.clipboard.writeText(pick.canonical_id).catch(() => undefined);
        }
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        const pick = results[cursor];
        if (pick) basket.toggle(pick.slug);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, results, cursor, navigate, onClose, basket]);

  if (!open) return null;

  return (
    <div className="v2-palette-scrim" onClick={onClose}>
      <div
        className="v2-palette"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Command palette"
      >
        <div className="v2-palette-input">
          <span className="v2-palette-input-icon">⌕</span>
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a model name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
          />
          <kbd>Esc</kbd>
        </div>

        <div className="v2-palette-results">
          {query && results.length === 0 ? (
            <div className="v2-palette-empty">No matches. Try a family name.</div>
          ) : (
            results.map((r, idx) => {
              const active = idx === cursor;
              return (
                <button
                  key={r.slug}
                  type="button"
                  className={`v2-palette-item${active ? ' is-active' : ''}`}
                  onMouseEnter={() => setCursor(idx)}
                  onClick={() => {
                    navigate(`/m/${r.slug}`);
                    onClose();
                  }}
                >
                  <span
                    className="v2-maker-dot"
                    style={{ background: makerColor(r.maker ?? null) }}
                    aria-hidden
                  />
                  <span className="v2-palette-item-name">{r.name}</span>
                  <span className="v2-palette-item-maker">
                    {r.maker ?? ''} · {r.family ?? ''}
                  </span>
                  <span className="v2-palette-item-price num">
                    {formatPrice(r.primary_input_price)}
                    <span className="v2-muted"> / {formatPrice(r.primary_output_price)}</span>
                  </span>
                </button>
              );
            })
          )}
        </div>

        <div className="v2-palette-footer">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd> navigate
          </span>
          <span>
            <kbd>⏎</kbd> open
          </span>
          <span>
            <kbd>⌘</kbd>
            <kbd>C</kbd> copy id
          </span>
          <span>
            <kbd>⌘</kbd>
            <kbd>D</kbd> compare
          </span>
        </div>
      </div>
    </div>
  );
}
