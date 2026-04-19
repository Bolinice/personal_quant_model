import { Box, Typography } from '@mui/material';
import { motion } from 'framer-motion';

interface MetricCardProps {
  label: string;
  value: string | number;
  color?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'flat';
  delay?: number;
}

export default function MetricCard({ label, value, color = '#22d3ee', icon, delay = 0 }: MetricCardProps) {
  const displayValue = typeof value === 'number' ? value.toLocaleString() : value;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, delay, ease: 'easeOut' }}
    >
      <Box
        sx={{
          backdropFilter: 'blur(16px)',
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid rgba(148, 163, 184, 0.1)',
          borderRadius: 3,
          p: 2.5,
          position: 'relative',
          overflow: 'hidden',
          cursor: 'default',
          transition: 'all 0.3s ease',
          '&:hover': {
            borderColor: `${color}44`,
            boxShadow: `0 0 24px ${color}18, inset 0 0 24px ${color}08`,
            transform: 'translateY(-2px)',
          },
          '&::after': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 2,
            background: `linear-gradient(90deg, transparent, ${color}88, transparent)`,
          },
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="body2" sx={{ color: '#94a3b8', mb: 0.5, fontSize: '0.8rem' }}>
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
                  fontWeight: 700,
                  color,
                  fontFamily: '"Inter", monospace',
                  letterSpacing: '-0.02em',
                }}
              >
                {displayValue}
              </Typography>
            </motion.div>
          </Box>
          {icon && (
            <Box sx={{ color: `${color}66`, '& .MuiSvgIcon-root': { fontSize: 36 } }}>
              {icon}
            </Box>
          )}
        </Box>
      </Box>
    </motion.div>
  );
}
