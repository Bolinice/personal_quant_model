import React from 'react';
import { Tooltip, Chip } from '@mui/material';

interface BacktestTagProps {
  size?: 'small' | 'default';
  showTooltip?: boolean;
}

const BacktestTag: React.FC<BacktestTagProps> = ({ size = 'small', showTooltip = true }) => {
  const tag = (
    <Chip
      label="回测"
      size={size === 'small' ? 'small' : 'medium'}
      sx={{
        backgroundColor: 'rgba(245, 158, 11, 0.15)',
        color: '#f59e0b',
        fontSize: size === 'small' ? 10 : 12,
        height: size === 'small' ? 20 : 24,
        fontWeight: 600,
      }}
    />
  );

  if (showTooltip) {
    return (
      <Tooltip title="此数据基于历史回测，不代表未来收益" arrow>
        {tag}
      </Tooltip>
    );
  }

  return tag;
};

export default BacktestTag;
