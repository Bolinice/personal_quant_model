import { Chip, ChipProps } from '@mui/material';

const NEON_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  cyan: { bg: 'rgba(34, 211, 238, 0.12)', border: 'rgba(34, 211, 238, 0.35)', text: '#22d3ee' },
  blue: { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.35)', text: '#3b82f6' },
  purple: { bg: 'rgba(139, 92, 246, 0.12)', border: 'rgba(139, 92, 246, 0.35)', text: '#8b5cf6' },
  green: { bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.35)', text: '#10b981' },
  red: { bg: 'rgba(244, 63, 94, 0.12)', border: 'rgba(244, 63, 94, 0.35)', text: '#f43f5e' },
  amber: { bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.35)', text: '#f59e0b' },
  indigo: { bg: 'rgba(99, 102, 241, 0.12)', border: 'rgba(99, 102, 241, 0.35)', text: '#6366f1' },
  default: { bg: 'rgba(148, 163, 184, 0.08)', border: 'rgba(148, 163, 184, 0.2)', text: '#94a3b8' },
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
        fontWeight: 600,
        fontSize: '0.75rem',
        '& .MuiChip-label': {
          px: 1.5,
        },
      }}
    />
  );
}
