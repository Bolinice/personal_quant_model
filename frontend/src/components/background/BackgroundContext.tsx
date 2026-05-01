import { createContext, useState, useCallback, type ReactNode } from 'react';

export interface ConstellationTheme {
  id: string;
  /** Display name (i18n key: `bgTheme.${id}`) */
  name: string;
  /** Time-of-day label (i18n key: `bgTime.${id}`) */
  timeLabel: string;
  /** Emoji icon for the picker */
  icon: string;
  /** Base background color */
  bgColor: string;
  /** Star color (r, g, b) */
  starColor: [number, number, number];
  /** Nebula gradient stops */
  nebula: string;
  /** Shooting star color (r, g, b) */
  shootingColor: [number, number, number];
  /** Star count multiplier */
  starDensity: number;
  /** Twinkle speed multiplier */
  twinkleSpeed: number;
}

export const CONSTELLATION_THEMES: ConstellationTheme[] = [
  {
    id: 'galaxy',
    name: 'bgTheme.galaxy',
    timeLabel: 'bgTime.galaxy',
    icon: '🌌',
    bgColor: '#030712',
    starColor: [200, 220, 255],
    nebula:
      'radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.08) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(139,92,246,0.06) 0%, transparent 50%)',
    shootingColor: [200, 230, 255],
    starDensity: 1,
    twinkleSpeed: 1,
  },
  {
    id: 'taurus',
    name: 'bgTheme.taurus',
    timeLabel: 'bgTime.taurus',
    icon: '♉',
    bgColor: '#0a0a1a',
    starColor: [255, 200, 140],
    nebula:
      'radial-gradient(ellipse at 30% 60%, rgba(245,158,11,0.10) 0%, transparent 55%), radial-gradient(ellipse at 70% 30%, rgba(251,191,36,0.06) 0%, transparent 50%)',
    shootingColor: [255, 210, 160],
    starDensity: 0.8,
    twinkleSpeed: 0.7,
  },
  {
    id: 'leo',
    name: 'bgTheme.leo',
    timeLabel: 'bgTime.leo',
    icon: '♌',
    bgColor: '#0d0a18',
    starColor: [255, 180, 100],
    nebula:
      'radial-gradient(ellipse at 50% 40%, rgba(249,115,22,0.09) 0%, transparent 55%), radial-gradient(ellipse at 20% 70%, rgba(251,146,60,0.06) 0%, transparent 50%)',
    shootingColor: [255, 190, 120],
    starDensity: 0.9,
    twinkleSpeed: 0.85,
  },
  {
    id: 'virgo',
    name: 'bgTheme.virgo',
    timeLabel: 'bgTime.virgo',
    icon: '♍',
    bgColor: '#080e1a',
    starColor: [180, 210, 255],
    nebula:
      'radial-gradient(ellipse at 40% 50%, rgba(99,102,241,0.08) 0%, transparent 55%), radial-gradient(ellipse at 75% 25%, rgba(129,140,248,0.05) 0%, transparent 50%)',
    shootingColor: [190, 215, 255],
    starDensity: 1.1,
    twinkleSpeed: 0.9,
  },
  {
    id: 'scorpio',
    name: 'bgTheme.scorpio',
    timeLabel: 'bgTime.scorpio',
    icon: '♏',
    bgColor: '#0f0810',
    starColor: [255, 140, 160],
    nebula:
      'radial-gradient(ellipse at 60% 55%, rgba(244,63,94,0.10) 0%, transparent 55%), radial-gradient(ellipse at 25% 30%, rgba(168,85,247,0.07) 0%, transparent 50%)',
    shootingColor: [255, 150, 170],
    starDensity: 1.2,
    twinkleSpeed: 1.1,
  },
  {
    id: 'aquarius',
    name: 'bgTheme.aquarius',
    timeLabel: 'bgTime.aquarius',
    icon: '♒',
    bgColor: '#050a14',
    starColor: [120, 200, 255],
    nebula:
      'radial-gradient(ellipse at 35% 45%, rgba(34,211,238,0.09) 0%, transparent 55%), radial-gradient(ellipse at 80% 60%, rgba(6,182,212,0.06) 0%, transparent 50%)',
    shootingColor: [140, 210, 255],
    starDensity: 1.3,
    twinkleSpeed: 0.8,
  },
  {
    id: 'pisces',
    name: 'bgTheme.pisces',
    timeLabel: 'bgTime.pisces',
    icon: '♓',
    bgColor: '#06060f',
    starColor: [160, 180, 255],
    nebula:
      'radial-gradient(ellipse at 45% 55%, rgba(139,92,246,0.10) 0%, transparent 55%), radial-gradient(ellipse at 70% 30%, rgba(99,102,241,0.06) 0%, transparent 50%)',
    shootingColor: [170, 190, 255],
    starDensity: 1.4,
    twinkleSpeed: 0.6,
  },
];

const STORAGE_KEY = 'bg_theme';

interface BackgroundContextValue {
  theme: ConstellationTheme;
  setThemeById: (id: string) => void;
}

export const BackgroundContext = createContext<BackgroundContextValue>({
  theme: CONSTELLATION_THEMES[0],
  setThemeById: () => {
    // Default no-op
  },
});

export function BackgroundProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeId] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && CONSTELLATION_THEMES.some((t) => t.id === saved)) return saved;
    } catch {
      // Ignore localStorage errors
    }
    return 'galaxy';
  });

  const theme = CONSTELLATION_THEMES.find((t) => t.id === themeId) || CONSTELLATION_THEMES[0];

  const setThemeById = useCallback((id: string) => {
    if (CONSTELLATION_THEMES.some((t) => t.id === id)) {
      setThemeId(id);
      try {
        localStorage.setItem(STORAGE_KEY, id);
      } catch {
        // Ignore localStorage errors
      }
    }
  }, []);

  return (
    <BackgroundContext.Provider value={{ theme, setThemeById }}>
      {children}
    </BackgroundContext.Provider>
  );
}

export { useBackground } from './hooks';
