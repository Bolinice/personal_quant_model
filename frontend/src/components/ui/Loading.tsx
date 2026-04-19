import { Box } from '@mui/material';
import { motion } from 'framer-motion';

export default function Loading() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 8 }}>
      <Box sx={{ position: 'relative', width: 48, height: 48 }}>
        {/* Outer ring */}
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            border: '2px solid transparent',
            borderTopColor: '#22d3ee',
            borderRightColor: '#8b5cf6',
          }}
        />
        {/* Inner glow */}
        <motion.div
          animate={{ scale: [0.8, 1.1, 0.8], opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            position: 'absolute',
            inset: 8,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(34,211,238,0.3), transparent)',
          }}
        />
      </Box>
    </Box>
  );
}
