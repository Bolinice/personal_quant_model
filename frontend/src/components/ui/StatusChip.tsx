import { Chip } from '@mui/material';
import { motion } from 'framer-motion';

interface StatusChipProps {
  status: 'active' | 'inactive' | 'draft' | 'archived' | string;
  label?: string;
  size?: 'small' | 'medium';
}

const statusConfig: Record<
  string,
  { label: string; color: string; bgColor: string; borderColor: string }
> = {
  active: {
    label: '运行中',
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.1)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  inactive: {
    label: '已停用',
    color: '#64748b',
    bgColor: 'rgba(100, 116, 139, 0.1)',
    borderColor: 'rgba(100, 116, 139, 0.3)',
  },
  draft: {
    label: '草稿',
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.1)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  archived: {
    label: '已归档',
    color: '#6366f1',
    bgColor: 'rgba(99, 102, 241, 0.1)',
    borderColor: 'rgba(99, 102, 241, 0.3)',
  },
};

export default function StatusChip({ status, label, size = 'small' }: StatusChipProps) {
  const config = statusConfig[status] || statusConfig.inactive;
  const displayLabel = label || config.label;

  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <Chip
        label={displayLabel}
        size={size}
        sx={{
          color: config.color,
          backgroundColor: config.bgColor,
          border: `1px solid ${config.borderColor}`,
          fontWeight: 600,
          fontSize: size === 'small' ? '0.75rem' : '0.875rem',
          height: size === 'small' ? '24px' : '28px',
          borderRadius: '6px',
          '& .MuiChip-label': {
            px: 1.5,
          },
        }}
      />
    </motion.div>
  );
}
