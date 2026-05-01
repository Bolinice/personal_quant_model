import { Suspense } from 'react';
import type { ReactNode } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';

/**
 * 路由懒加载的 Suspense 包装器
 */
interface LazyLoadWrapperProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function LazyLoadWrapper({ children, fallback }: LazyLoadWrapperProps) {
  return <Suspense fallback={fallback || <DefaultLoadingFallback />}>{children}</Suspense>;
}

/**
 * 默认加载占位符
 */
function DefaultLoadingFallback() {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        gap: 2,
      }}
    >
      <CircularProgress size={40} sx={{ color: '#22d3ee' }} />
      <Typography sx={{ color: '#64748b', fontSize: '0.875rem' }}>加载中...</Typography>
    </Box>
  );
}

/**
 * 页面级加载占位符
 */
export function PageLoadingFallback() {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a0e1a 0%, #1a1f2e 100%)',
      }}
    >
      <Box sx={{ textAlign: 'center' }}>
        <CircularProgress size={48} sx={{ color: '#22d3ee', mb: 2 }} />
        <Typography sx={{ color: '#94a3b8', fontSize: '0.9rem' }}>正在加载页面...</Typography>
      </Box>
    </Box>
  );
}

/**
 * 组件级加载占位符
 */
export function ComponentLoadingFallback() {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '200px',
        p: 3,
      }}
    >
      <CircularProgress size={32} sx={{ color: '#22d3ee' }} />
    </Box>
  );
}
