import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { LocaleProvider, useI18n } from './localeContext';

function Probe() {
  const { locale, t, toggle } = useI18n();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="brand">{t('brand.tagline')}</span>
      <span data-testid="hero">
        {t('hero.meta_matching_fmt', { count: 3, query: 'gpt', total: 10 })}
      </span>
      <button onClick={toggle}>toggle</button>
    </div>
  );
}

describe('LocaleProvider', () => {
  it('defaults to English (no auto zh detection)', () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId('locale').textContent).toBe('en');
    expect(screen.getByTestId('brand').textContent).toBe('v2 preview');
  });

  it('toggles to Chinese and persists', async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    await user.click(screen.getByText('toggle'));
    expect(screen.getByTestId('locale').textContent).toBe('zh');
    expect(screen.getByTestId('brand').textContent).toBe('v2 预览');
    expect(localStorage.getItem('model-price-v2:locale')).toBe('zh');
  });

  it('interpolates {name} placeholders', () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByTestId('hero').textContent).toBe('3 matching "gpt" of 10');
  });

  it('updates <html lang>', async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(document.documentElement.lang).toBe('en');
    await user.click(screen.getByText('toggle'));
    expect(document.documentElement.lang).toBe('zh-CN');
  });
});
