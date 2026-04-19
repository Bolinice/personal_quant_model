import { Box, Table, TableProps } from '@mui/material';
import { motion } from 'framer-motion';

interface GlassTableProps extends TableProps {
  animate?: boolean;
}

export default function GlassTable({ children, animate = true, ...props }: GlassTableProps) {
  return (
    <motion.div
      {...(animate ? {
        initial: { opacity: 0, y: 12 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.4, ease: 'easeOut' },
      } : {})}
    >
      <Box
        sx={{
          backdropFilter: 'blur(16px)',
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid rgba(148, 163, 184, 0.1)',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <Table {...props}>{children}</Table>
      </Box>
    </motion.div>
  );
}
