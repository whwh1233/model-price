import { useTheme } from '../themeContext';
import type { ThemeMode } from '../themeContext';
import './ThemeToggle.css';

const LABELS: Record<ThemeMode, string> = {
  dark: '● Dark',
  light: '○ Light',
  system: '◐ System',
};

const NEXT_HINT: Record<ThemeMode, string> = {
  dark: 'Switch to Light',
  light: 'Switch to System',
  system: 'Switch to Dark',
};

export function ThemeToggle() {
  const { mode, cycle } = useTheme();
  return (
    <button
      type="button"
      className="v2-theme-toggle"
      onClick={cycle}
      title={NEXT_HINT[mode]}
      aria-label={`Theme: ${mode}. ${NEXT_HINT[mode]}`}
    >
      {LABELS[mode]}
    </button>
  );
}
