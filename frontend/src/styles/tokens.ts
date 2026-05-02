/**
 * Design Tokens - Premium Design System
 * 参考 Linear, Vercel, Stripe 的设计语言
 */

// 颜色系统 - 更精致的配色
export const colors = {
  // 品牌色 - 更沉稳优雅
  brand: {
    primary: '#3b82f6',        // 蓝色主色 (更专业)
    primaryLight: '#60a5fa',
    primaryDark: '#2563eb',
    secondary: '#8b5cf6',      // 紫色辅助色
    secondaryLight: '#a78bfa',
    secondaryDark: '#7c3aed',
    accent: '#06b6d4',         // 青色强调色
    accentLight: '#22d3ee',
  },

  // 语义色 - 更柔和的饱和度
  semantic: {
    success: '#10b981',
    successLight: '#34d399',
    successBg: 'rgba(16, 185, 129, 0.08)',
    error: '#ef4444',
    errorLight: '#f87171',
    errorBg: 'rgba(239, 68, 68, 0.08)',
    warning: '#f59e0b',
    warningLight: '#fbbf24',
    warningBg: 'rgba(245, 158, 11, 0.08)',
    info: '#3b82f6',
    infoLight: '#60a5fa',
    infoBg: 'rgba(59, 130, 246, 0.08)',
  },

  // 表面色 - 更丰富的层次
  surface: {
    background: '#0a0a0a',           // 更深的背景
    backgroundElevated: '#0f0f0f',   // 轻微提升
    glass: 'rgba(17, 17, 19, 0.7)',  // 更精致的玻璃效果
    glassBorder: 'rgba(255, 255, 255, 0.06)', // 更微妙的边框
    elevated: 'rgba(20, 20, 22, 0.9)',
    elevatedHover: 'rgba(24, 24, 27, 0.9)',
    drawer: 'rgba(12, 12, 14, 0.95)',
    appBar: 'rgba(10, 10, 12, 0.8)',
    card: 'rgba(18, 18, 20, 0.8)',
    cardHover: 'rgba(22, 22, 24, 0.9)',
  },

  // 文本色 - 更精细的层级
  text: {
    primary: '#fafafa',           // 更亮的主文本
    secondary: '#a1a1aa',         // 中性灰
    tertiary: '#71717a',          // 次要文本
    disabled: '#52525b',          // 禁用状态
    muted: '#3f3f46',            // 极弱文本
    inverse: '#18181b',          // 反色文本
  },

  // 边框色 - 更微妙的层次
  border: {
    subtle: 'rgba(255, 255, 255, 0.04)',
    default: 'rgba(255, 255, 255, 0.08)',
    medium: 'rgba(255, 255, 255, 0.12)',
    strong: 'rgba(255, 255, 255, 0.18)',
    brand: 'rgba(59, 130, 246, 0.3)',
  },

  // 交互状态 - 更精致的反馈
  interaction: {
    hover: 'rgba(255, 255, 255, 0.05)',
    hoverStrong: 'rgba(255, 255, 255, 0.08)',
    active: 'rgba(255, 255, 255, 0.1)',
    focus: 'rgba(59, 130, 246, 0.4)',
    focusRing: 'rgba(59, 130, 246, 0.3)',
  },

  // 滚动条
  scrollbar: {
    track: 'transparent',
    thumb: 'rgba(255, 255, 255, 0.1)',
    thumbHover: 'rgba(255, 255, 255, 0.2)',
  },

  // 渐变 - 更优雅的渐变
  gradient: {
    primary: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
    primaryHover: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
    subtle: 'linear-gradient(180deg, rgba(255, 255, 255, 0.05) 0%, transparent 100%)',
    glow: 'radial-gradient(circle at 50% 0%, rgba(59, 130, 246, 0.15), transparent 50%)',
  },

  // 叠加层
  overlay: {
    light: 'rgba(255, 255, 255, 0.02)',
    medium: 'rgba(255, 255, 255, 0.05)',
    strong: 'rgba(255, 255, 255, 0.08)',
  },
} as const;

// 字体系统 - 更专业的排版
export const typography = {
  fontFamily: {
    base: '"Inter var", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    display: '"Cal Sans", "Inter var", "Inter", sans-serif', // 用于大标题
    mono: '"JetBrains Mono", "Fira Code", Consolas, Monaco, monospace',
  },

  fontSize: {
    xs: '0.6875rem',   // 11px
    sm: '0.8125rem',   // 13px
    base: '0.9375rem', // 15px
    md: '1rem',        // 16px
    lg: '1.125rem',    // 18px
    xl: '1.25rem',     // 20px
    '2xl': '1.5rem',   // 24px
    '3xl': '1.875rem', // 30px
    '4xl': '2.25rem',  // 36px
    '5xl': '3rem',     // 48px
    '6xl': '3.75rem',  // 60px
  },

  fontWeight: {
    light: 300,
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
    black: 900,
  },

  lineHeight: {
    none: 1,
    tight: 1.25,
    snug: 1.375,
    normal: 1.5,
    relaxed: 1.625,
    loose: 2,
  },

  letterSpacing: {
    tighter: '-0.04em',
    tight: '-0.02em',
    normal: '0',
    wide: '0.02em',
    wider: '0.04em',
    widest: '0.08em',
  },
} as const;

// 间距系统 (基于 4px 网格，更精细)
export const spacing = {
  0: 0,
  px: '1px',
  0.5: '0.125rem',  // 2px
  1: '0.25rem',     // 4px
  1.5: '0.375rem',  // 6px
  2: '0.5rem',      // 8px
  2.5: '0.625rem',  // 10px
  3: '0.75rem',     // 12px
  3.5: '0.875rem',  // 14px
  4: '1rem',        // 16px
  5: '1.25rem',     // 20px
  6: '1.5rem',      // 24px
  7: '1.75rem',     // 28px
  8: '2rem',        // 32px
  9: '2.25rem',     // 36px
  10: '2.5rem',     // 40px
  12: '3rem',       // 48px
  14: '3.5rem',     // 56px
  16: '4rem',       // 64px
  20: '5rem',       // 80px
  24: '6rem',       // 96px
  28: '7rem',       // 112px
  32: '8rem',       // 128px
} as const;

// 圆角系统 - 更精致的圆角
export const borderRadius = {
  none: 0,
  xs: '0.25rem',    // 4px
  sm: '0.375rem',   // 6px
  base: '0.5rem',   // 8px
  md: '0.625rem',   // 10px
  lg: '0.75rem',    // 12px
  xl: '1rem',       // 16px
  '2xl': '1.25rem', // 20px
  '3xl': '1.5rem',  // 24px
  full: '9999px',
} as const;

// 阴影系统 - 更精致的阴影
export const shadows = {
  xs: '0 1px 2px 0 rgba(0, 0, 0, 0.3)',
  sm: '0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.4)',
  base: '0 2px 4px -1px rgba(0, 0, 0, 0.4), 0 4px 6px -1px rgba(0, 0, 0, 0.3)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.3)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3)',
  '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
  inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.3)',

  // 光晕效果 - 更微妙
  glow: '0 0 20px rgba(59, 130, 246, 0.2), 0 0 40px rgba(59, 130, 246, 0.1)',
  glowPurple: '0 0 20px rgba(139, 92, 246, 0.2), 0 0 40px rgba(139, 92, 246, 0.1)',
  glowSubtle: '0 0 15px rgba(59, 130, 246, 0.15)',
} as const;

// 效果系统 - 更精致的模糊
export const effects = {
  blur: {
    xs: 'blur(2px)',
    sm: 'blur(4px)',
    base: 'blur(8px)',
    md: 'blur(12px)',
    lg: 'blur(16px)',
    xl: 'blur(24px)',
    '2xl': 'blur(40px)',
  },

  // 背景模糊（用于玻璃态射）
  backdropBlur: {
    sm: 'blur(8px) saturate(180%)',
    base: 'blur(12px) saturate(180%)',
    md: 'blur(16px) saturate(180%)',
    lg: 'blur(20px) saturate(180%)',
    xl: 'blur(24px) saturate(180%)',
  },
} as const;

// 过渡动画 - 更流畅的动画
export const transitions = {
  duration: {
    instant: '50ms',
    fast: '150ms',
    base: '200ms',
    medium: '300ms',
    slow: '400ms',
    slower: '600ms',
  },
  easing: {
    default: 'cubic-bezier(0.4, 0, 0.2, 1)',
    linear: 'linear',
    in: 'cubic-bezier(0.4, 0, 1, 1)',
    out: 'cubic-bezier(0, 0, 0.2, 1)',
    inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
    spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
  },
} as const;

// Z-index 层级
export const zIndex = {
  hide: -1,
  base: 0,
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  modalBackdrop: 1040,
  modal: 1050,
  popover: 1060,
  tooltip: 1070,
  notification: 1080,
} as const;

// 断点系统 (响应式设计)
export const breakpoints = {
  xs: 0,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const;

// 导出统一的 tokens 对象
export const tokens = {
  colors,
  typography,
  spacing,
  borderRadius,
  shadows,
  effects,
  transitions,
  zIndex,
  breakpoints,
} as const;
