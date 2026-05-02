import { Box, BoxProps } from '@mui/material';
import { motion } from 'framer-motion';
import { tokens } from '../../styles/tokens';

interface GlassPanelProps extends BoxProps {
  glow?: boolean;
  glowColor?: string;
  animate?: boolean;
  variant?: 'default' | 'elevated' | 'subtle';
}

export default function GlassPanel({
  children,
  glow = false,
  glowColor = tokens.colors.brand.primary,
  animate = true,
  variant = 'default',
  sx,
  ...props
}: GlassPanelProps) {
  // 根据变体选择样式
  const variantStyles = {
    default: {
      backdropFilter: tokens.effects.backdropBlur.base,
      backgroundColor: tokens.colors.surface.glass,
      border: `1px solid ${tokens.colors.border.default}`,
      boxShadow: tokens.shadows.sm,
    },
    elevated: {
      backdropFilter: tokens.effects.backdropBlur.md,
      backgroundColor: tokens.colors.surface.elevated,
      border: `1px solid ${tokens.colors.border.medium}`,
      boxShadow: tokens.shadows.md,
    },
    subtle: {
      backdropFilter: tokens.effects.backdropBlur.sm,
      backgroundColor: tokens.colors.surface.card,
      border: `1px solid ${tokens.colors.border.subtle}`,
      boxShadow: 'none',
    },
  };

  const panel = (
    <Box
      sx={{
        ...variantStyles[variant],
        borderRadius: tokens.borderRadius.xl,
        p: 3,
        position: 'relative',
        overflow: 'hidden',
        transition: `all ${tokens.transitions.duration.base} ${tokens.transitions.easing.default}`,

        // 顶部微妙的光效
        '&::before': glow ? {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '1px',
          background: `linear-gradient(90deg, transparent, ${glowColor}40, transparent)`,
          pointerEvents: 'none',
        } : undefined,

        // 悬停时的光晕效果
        '&:hover': glow ? {
          borderColor: `${glowColor}30`,
          boxShadow: `0 0 20px ${glowColor}15, ${tokens.shadows.md}`,
          transform: 'translateY(-2px)',
        } : {
          borderColor: tokens.colors.border.medium,
        },

        // 内部微妙的渐变叠加
        '&::after': {
          content: '""',
          position: 'absolute',
          inset: 0,
          background: tokens.colors.gradient.subtle,
          pointerEvents: 'none',
          opacity: 0.5,
        },

        // 确保内容在叠加层之上
        '& > *': {
          position: 'relative',
          zIndex: 1,
        },

        ...sx,
      }}
      {...props}
    >
      {children}
    </Box>
  );

  if (!animate) return panel;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.4,
        ease: [0.4, 0, 0.2, 1],
      }}
    >
      {panel}
    </motion.div>
  );
}
