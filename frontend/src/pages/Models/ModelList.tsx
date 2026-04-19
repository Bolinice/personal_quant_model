import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Grid, Typography, Snackbar, Alert } from '@mui/material';
import { motion } from 'framer-motion';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import LockIcon from '@mui/icons-material/Lock';
import { stockPoolApi } from '@/api';
import type { StockPool } from '@/api';
import { PageHeader, GlassPanel, NeonChip } from '@/components/ui';

const FREE_POOLS = new Set(['HS300', 'ZZ500']);

const POOL_COLORS: Record<string, string> = {
  HS300: '#22d3ee', ZZ500: '#8b5cf6', ZZ1000: '#10b981', ALL_A: '#f59e0b',
};

const POOL_NEON: Record<string, 'cyan' | 'purple' | 'green' | 'amber'> = {
  HS300: 'cyan', ZZ500: 'purple', ZZ1000: 'green', ALL_A: 'amber',
};

export default function ModelList() {
  const navigate = useNavigate();
  const [pools, setPools] = useState<StockPool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    stockPoolApi.list({ limit: 200 })
      .then((res) => setPools(res.data.filter((p) => p.is_active)))
      .catch(() => setError('加载股票池失败'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Box>
      <PageHeader title="模型管理" />

      {loading ? <Typography>加载中...</Typography> : (
        <Grid container spacing={2.5}>
          {pools.map((pool, i) => {
            const color = POOL_COLORS[pool.pool_code] || '#94a3b8';
            const neon = POOL_NEON[pool.pool_code];
            const isPaid = !FREE_POOLS.has(pool.pool_code);
            return (
              <Grid size={{ xs: 12, sm: 6 }} key={pool.pool_code}>
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.08 }}
                >
                  <GlassPanel
                    glow
                    glowColor={color}
                    animate={false}
                    onClick={() => navigate(`/models/${pool.pool_code}`)}
                    sx={{
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      transition: 'all 0.3s ease',
                      '&:hover': {
                        transform: 'translateY(-2px)',
                        boxShadow: `0 0 24px ${color}15`,
                      },
                    }}
                  >
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Typography sx={{ fontWeight: 700, color: '#e2e8f0', fontSize: '1.1rem' }}>
                          {pool.pool_name}
                        </Typography>
                        {neon && <NeonChip label="启用" size="small" neonColor={neon} />}
                        {isPaid && (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.25, borderRadius: 1, background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                            <LockIcon sx={{ fontSize: 14, color: '#f59e0b' }} />
                            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: '#f59e0b' }}>付费</Typography>
                          </Box>
                        )}
                      </Box>
                      <Typography variant="body2" sx={{ color: '#64748b' }}>
                        {pool.description || `${pool.pool_name}增强策略`}
                      </Typography>
                    </Box>
                    <ArrowForwardIcon sx={{ color: `${color}66`, transition: 'color 0.2s' }} />
                  </GlassPanel>
                </motion.div>
              </Grid>
            );
          })}
          {pools.length === 0 && (
            <Grid size={12}>
              <Typography sx={{ textAlign: 'center', color: '#64748b', py: 4 }}>暂无股票池数据</Typography>
            </Grid>
          )}
        </Grid>
      )}

      <Snackbar open={!!error} autoHideDuration={3000} onClose={() => setError('')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
    </Box>
  );
}