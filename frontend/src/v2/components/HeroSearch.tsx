import { useEffect, useRef } from 'react';
import './HeroSearch.css';

interface HeroSearchProps {
  value: string;
  onChange: (next: string) => void;
  resultCount: number;
  totalCount: number;
}

export function HeroSearch({
  value,
  onChange,
  resultCount,
  totalCount,
}: HeroSearchProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    if (typeof window !== 'undefined' && window.innerWidth < 720) return;
    if (document.activeElement === document.body) {
      el.focus();
    }
  }, []);

  return (
    <section className="v2-hero">
      <h1 className="v2-hero-title">
        Compare <span className="num">{totalCount}</span> LLMs from every major provider.
      </h1>
      <p className="v2-hero-sub">
        Real pricing, real capabilities. Keyboard-first. Shareable links. Built for devs
        who read configs more than marketing pages.
      </p>

      <div className="v2-hero-search">
        <span className="v2-hero-search-icon">⌕</span>
        <input
          ref={inputRef}
          type="text"
          placeholder="Search by name, family, or model_id…"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
        />
        <span className="v2-hero-search-hint" aria-hidden>
          ⌘K
        </span>
      </div>

      <div className="v2-hero-meta">
        <span className="num">{resultCount}</span>
        {value
          ? ` matching "${value}" of ${totalCount}`
          : ` of ${totalCount} shown`}
      </div>
    </section>
  );
}
