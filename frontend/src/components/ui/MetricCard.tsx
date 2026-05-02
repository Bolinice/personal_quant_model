import { Box, Typography } from '@mui/material';
import { motion } from 'framer-motion';
import { tokens } from '../../styles/tokens';

interface MetricCardProps {
  label: string;
  value: string | number;
  color?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'flat';
  delay?: number;
}

export default function MetricCard({
  label,
  value,
  color = tokens.colors.brand.primary,
  icon,
  delay = 0,
}: MetricCardProps) {
  const displayValue = typeof value === 'number' ? value.toLocaleString() : value;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, delay, ease: [0.4, 0, 0.2, 1] }}
    >
      <Box
        sx={{
          backdropFilter: tokens.effects.backdropBlur.base,
          backgroundColor: tokens.colors.surface.card,
          border: `1px solid ${tokens.colors.border.default}`,
          borderRadius: tokens.borderRadius.xl,
          p: 3,
          position: 'relative',
          overflow: 'hidden',
          cursor: 'default',
          transition: `all ${tokens.transitions.duration.base} ${tokens.transitions.easing.default}`,

          // 顶部微妙的渐变线
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '1px',
            background: `linear-gradient(90deg, transparent, ${color}40, transparent)`,
            pointerEvents: 'none',
          },

          // 悬停效果
          '&:hover': {
            backgroundColor: tokens.colors.surface.cardHover,
            borderColor: `${color}30`,
            boxShadow: `0 0 20px ${color}10, ${tokens.shadows.md}`,
            transform: 'translateY(-2px)',
          },

          // 内部微妙的渐变叠加
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: 0,
            background: tokens.colors.gradient.subtle,
            pointerEvents: 'none',
            opacity: 0.3,
          },
        }}
      >
        <Box sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          position: 'relative',
          zIndex: 1,
        }}>
          <Box>
            <Typography
              variant="body2"
              sx={{
                color: tokens.colors.text.tertiary,
                mb: 1,
                fontSize: tokens.typography.fontSize.xs,
                fontWeight: tokens.typography.fontWeight.medium,
                textTransform: 'uppercase',
                letterSpacing: tokens.typography.letterSpacing.wider,
              }}
            >
              {label}
            </Typography>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: delay + 0.2 }}
            >
              <Typography
                variant="h4"
                sx={{
                  fontWeight: tokens.typography.fontWeight.bold,
                  color,
                  fontFamily: tokens.typography.fontFamily.display,
                  letterSpacing: tokens.typography.letterSpacing.tight,
                  fontSize: '1.75rem',
                }}
              >
                {displayValue}
              </Typography>
            </motion.div>
          </Box>
          {icon && (
            <Box
              sx={{
                color: `${color}50`,
                opacity: 0.6,
                '& .MuiSvgIcon-root': { fontSize: 32 }
              }}
            >
              {icon}
            </Box>
          )}
        </Box>
      </Box>
    </motion.div>
  );
}
