import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { LocaleProvider, useI18n } from './localeContext';

function Probe() {
  const { locale, t, toggle } = useI18n();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="sample">{t('nav.search_placeholder')}</span>
      <span data-testid="hero">
        {t('hero.meta_matching_fmt', { count: 3, query: 'gpt', total: 10 })}
      </span>
      <button onClick={toggle}>toggle</button>
    </div>
  );
}

describe('LocaleProvider', () => {
  it('defaults to Chinese', () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId('locale').textContent).toBe('zh');
    expect(screen.getByTestId('sample').textContent).toBe('搜索模型…');
  });

  it('toggles to English and persists', async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    await user.click(screen.getByText('toggle'));
    expect(screen.getByTestId('locale').textContent).toBe('en');
    expect(screen.getByTestId('sample').textContent).toBe('Search models…');
    expect(localStorage.getItem('model-price-v2:locale')).toBe('en');
  });

  it('interpolates {name} placeholders', () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId('hero').textContent).toBe('3 个模型匹配 "gpt",共 10');
  });

  it('updates <html lang>', async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(document.documentElement.lang).toBe('zh-CN');
    await user.click(screen.getByText('toggle'));
    expect(document.documentElement.lang).toBe('en');
  });
});
