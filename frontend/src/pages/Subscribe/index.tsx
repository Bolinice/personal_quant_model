import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button, Snackbar, Alert } from '@mui/material';
import { motion } from 'framer-motion';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { PageHeader, GlassPanel, NeonChip } from '@/components/ui';
import { subscriptionApi } from '@/api';

const FEATURES = [
  '中证1000增强策略完整报告',
  '全A股增强策略完整报告',
  '每日持仓评分与排名',
  '策略表现与风险指标',
  'IC/换手率等核心数据',
];

function getUserId(): number {
  return Number(localStorage.getItem('user_id') || '1');
}

export default function Subscribe() {
  const navigate = useNavigate();
  const [paying, setPaying] = useState(false);
  const [planId, setPlanId] = useState<number | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    // Load available plans
    subscriptionApi.listPlans()
      .then((res) => {
        const plans = res.data as Array<{ id: number; plan_name: string; price: number }>;
        if (plans.length > 0) setPlanId(plans[0].id);
      })
      .catch(() => {});
  }, []);

  const handlePay = async () => {
    if (!planId) return;
    setPaying(true);
    try {
      const res = await subscriptionApi.subscribe(getUserId(), planId);
      const data = res.data as { success: boolean; end_date: string; products: Array<{ product_name: string; status: string }> };
      if (data.success) {
        setSnackbar({ open: true, message: `订阅成功！有效期至 ${data.end_date}`, severity: 'success' });
        setTimeout(() => navigate('/models'), 1500);
      } else {
        setSnackbar({ open: true, message: '订阅失败，请重试', severity: 'error' });
      }
    } catch {
      setSnackbar({ open: true, message: '支付失败，请重试', severity: 'error' });
    } finally {
      setPaying(false);
    }
  };

  return (
    <Box>
      <PageHeader
        title="订阅解锁"
        actions={<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/models')}>返回</Button>}
      />

      <Box sx={{ maxWidth: 600, mx: 'auto' }}>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <GlassPanel glow glowColor="#f59e0b" sx={{ p: 4 }}>
            {/* Plan name */}
            <Typography
              variant="h4"
              sx={{
                fontWeight: 800,
                mb: 1,
                background: 'linear-gradient(135deg, #f59e0b, #f43f5e)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              策略报告专业版
            </Typography>
            <NeonChip label="热门" size="small" neonColor="amber" />

            {/* Price */}
            <Box sx={{ mt: 3, mb: 3, display: 'flex', alignItems: 'baseline', gap: 1 }}>
              <Typography sx={{ fontWeight: 800, fontSize: '3rem', color: '#f59e0b' }}>¥199</Typography>
              <Typography sx={{ color: '#94a3b8', fontSize: '1.1rem' }}>/月</Typography>
            </Box>

            {/* Features */}
            <Box sx={{ mb: 4 }}>
              {FEATURES.map((f, i) => (
                <Box
                  key={i}
                  component={motion.div}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.08 }}
                  sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}
                >
                  <CheckCircleIcon sx={{ color: '#10b981', fontSize: 20 }} />
                  <Typography sx={{ color: '#e2e8f0', fontSize: '0.95rem' }}>{f}</Typography>
                </Box>
              ))}
            </Box>

            {/* Free tier note */}
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                border: '1px solid rgba(34, 211, 238, 0.2)',
                background: 'rgba(34, 211, 238, 0.05)',
                mb: 3,
              }}
            >
              <Typography variant="body2" sx={{ color: '#22d3ee', fontWeight: 600, mb: 0.5 }}>
                免费版已包含
              </Typography>
              <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                沪深300、中证500增强策略报告
              </Typography>
            </Box>

            {/* Pay button */}
            <Button
              variant="contained"
              fullWidth
              size="large"
              onClick={handlePay}
              disabled={paying || !planId}
              sx={{
                py: 1.5,
                borderRadius: 2,
                fontWeight: 700,
                fontSize: '1.1rem',
                background: 'linear-gradient(135deg, #f59e0b, #f43f5e)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #fbbf24, #fb7185)',
                },
              }}
            >
              {paying ? '支付处理中...' : '立即订阅 ¥199/月'}
            </Button>
          </GlassPanel>
        </motion.div>
      </Box>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}