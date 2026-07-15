import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { ThemeProvider, useTheme } from './themeContext';

function Probe() {
  const { mode, resolved, cycle } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="resolved">{resolved}</span>
      <button onClick={cycle}>cycle</button>
    </div>
  );
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    // Stub matchMedia so themeContext's OS listener doesn't explode
    // in happy-dom (which doesn't implement matchMedia by default).
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }));
  });

  it('defaults to light', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('mode').textContent).toBe('light');
    expect(screen.getByTestId('resolved').textContent).toBe('light');
  });

  it('cycles light → system → dark → light', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    const btn = screen.getByText('cycle');
    expect(screen.getByTestId('mode').textContent).toBe('light');
    await user.click(btn);
    expect(screen.getByTestId('mode').textContent).toBe('system');
    await user.click(btn);
    expect(screen.getByTestId('mode').textContent).toBe('dark');
    await user.click(btn);
    expect(screen.getByTestId('mode').textContent).toBe('light');
  });

  it('persists the mode to localStorage', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    await user.click(screen.getByText('cycle')); // → system
    expect(localStorage.getItem('model-price-v2:theme')).toBe('system');
  });

  it('reflects theme on <html data-theme>', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
});
