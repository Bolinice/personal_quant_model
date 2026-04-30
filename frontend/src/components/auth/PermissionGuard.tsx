import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import { useAuth } from '@/contexts/AuthContext';

interface PermissionGuardProps {
  /** 需要的权限编码 */
  permission: string;
  children: React.ReactNode;
  /** 无权限时显示的提示文字 */
  fallbackText?: string;
}

/**
 * 权限守卫组件
 * 根据用户权限控制子组件是否可见，无权限时显示升级引导
 */
const PermissionGuard: React.FC<PermissionGuardProps> = ({
  permission,
  children,
  fallbackText,
}) => {
  const { user } = useAuth();
  const permissions: string[] = [];

  // 管理员直接通过
  if (user?.is_superuser) return <>{children}</>;

  // 有权限则渲染子组件
  if (permissions.includes(permission)) return <>{children}</>;

  // 无权限：显示升级引导
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: 6,
        gap: 2,
      }}
    >
      <LockIcon sx={{ fontSize: 48, color: '#64748b' }} />
      <Typography sx={{ color: '#94a3b8', fontSize: '0.9rem', textAlign: 'center' }}>
        {fallbackText || '此功能需要升级订阅方案'}
      </Typography>
      <Button
        variant="contained"
        href="/app/subscribe"
        sx={{
          mt: 1,
          borderRadius: 2,
          fontWeight: 700,
          background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
          '&:hover': { background: 'linear-gradient(135deg, #06b6d4, #7c3aed)' },
        }}
      >
        升级方案
      </Button>
    </Box>
  );
};

export default PermissionGuard;
