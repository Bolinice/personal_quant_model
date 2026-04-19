import { Box, BoxProps } from '@mui/material';
import { motion } from 'framer-motion';

interface GlassPanelProps extends BoxProps {
  glow?: boolean;
  glowColor?: string;
  animate?: boolean;
}

export default function GlassPanel({ children, glow, glowColor = '#22d3ee', animate = true, sx, ...props }: GlassPanelProps) {
  const panel = (
    <Box
      sx={{
        backdropFilter: 'blur(16px)',
        backgroundColor: 'rgba(15, 23, 42, 0.6)',
        border: '1px solid rgba(148, 163, 184, 0.1)',
        borderRadius: 3,
        p: 2.5,
        position: 'relative',
        overflow: 'hidden',
        ...(glow && {
          '&::before': {
            content: '""',
            position: 'absolute',
            inset: -1,
            borderRadius: 3,
            padding: 1,
            background: `linear-gradient(135deg, ${glowColor}33, transparent 60%)`,
            mask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
            maskComposite: 'exclude',
            WebkitMaskComposite: 'xor',
            pointerEvents: 'none',
          },
        }),
        '&:hover': glow ? {
          borderColor: `${glowColor}44`,
          boxShadow: `0 0 20px ${glowColor}15`,
        } : {},
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
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
    >
      {panel}
    </motion.div>
  );
}
