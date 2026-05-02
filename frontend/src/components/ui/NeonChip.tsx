import { Chip, ChipProps } from '@mui/material';
import { tokens } from '../../styles/tokens';

const NEON_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  cyan: {
    bg: `${tokens.colors.brand.primary}12`,
    border: `${tokens.colors.brand.primary}35`,
    text: tokens.colors.brand.primary
  },
  blue: {
    bg: tokens.colors.semantic.infoBg,
    border: `${tokens.colors.semantic.info}35`,
    text: tokens.colors.semantic.info
  },
  purple: {
    bg: `${tokens.colors.brand.secondary}12`,
    border: `${tokens.colors.brand.secondary}35`,
    text: tokens.colors.brand.secondary
  },
  green: {
    bg: tokens.colors.semantic.successBg,
    border: `${tokens.colors.semantic.success}35`,
    text: tokens.colors.semantic.success
  },
  red: {
    bg: tokens.colors.semantic.errorBg,
    border: `${tokens.colors.semantic.error}35`,
    text: tokens.colors.semantic.error
  },
  amber: {
    bg: tokens.colors.semantic.warningBg,
    border: `${tokens.colors.semantic.warning}35`,
    text: tokens.colors.semantic.warning
  },
  indigo: {
    bg: 'rgba(99, 102, 241, 0.12)',
    border: 'rgba(99, 102, 241, 0.35)',
    text: '#6366f1'
  },
  default: {
    bg: 'rgba(148, 163, 184, 0.08)',
    border: 'rgba(148, 163, 184, 0.2)',
    text: tokens.colors.text.secondary
  },
};

type NeonColor = keyof typeof NEON_COLORS;

interface NeonChipProps extends Omit<ChipProps, 'color'> {
  neonColor?: NeonColor;
}

export default function NeonChip({ neonColor = 'default', ...props }: NeonChipProps) {
  const c = NEON_COLORS[neonColor];

  return (
    <Chip
      {...props}
      sx={{
        backgroundColor: c.bg,
        border: `1px solid ${c.border}`,
        color: c.text,
        fontWeight: tokens.typography.fontWeight.semibold,
        fontSize: tokens.typography.fontSize.xs,
        '& .MuiChip-label': {
          px: 1.5,
        },
      }}
    />
  );
}
