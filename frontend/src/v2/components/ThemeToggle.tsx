import { useTheme } from '../themeContext';
import type { ThemeMode } from '../themeContext';
import { useI18n } from '../i18n/localeContext';
import './ThemeToggle.css';

const ICONS: Record<ThemeMode, string> = {
  dark: '●',
  light: '○',
  system: '◐',
};

const NEXT: Record<ThemeMode, ThemeMode> = {
  dark: 'light',
  light: 'system',
  system: 'dark',
};

export function ThemeToggle() {
  const { mode, cycle } = useTheme();
  const { t } = useI18n();
  const currentLabel = t(`theme.${mode}` as 'theme.dark' | 'theme.light' | 'theme.system');
  const nextLabel = t(`theme.${NEXT[mode]}` as 'theme.dark' | 'theme.light' | 'theme.system');
  const title = t('theme.next_fmt', { next: nextLabel });
  return (
    <button
      type="button"
      className="v2-theme-toggle"
      onClick={cycle}
      title={title}
      aria-label={title}
    >
      {ICONS[mode]} {currentLabel}
    </button>
  );
}
