export const STORAGE_KEY = 'background_theme';

export const BACKGROUND_THEMES = [
  { id: 'starfield', label: '星空' },
  { id: 'gradient', label: '渐变' },
  { id: 'particles', label: '粒子' },
] as const;

export type BackgroundThemeId = (typeof BACKGROUND_THEMES)[number]['id'];
