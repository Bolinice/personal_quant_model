import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button, Snackbar, Alert, Chip } from '@mui/material';
import { motion } from 'framer-motion';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import StarIcon from '@mui/icons-material/Star';
import { PageHeader, GlassPanel } from '@/components/ui';
import { subscriptionApi } from '@/api';
import type { SubscriptionPlan } from '@/api/types/subscriptions';
import { useT } from '@/i18n';

function getUserId(): number {
  return Number(localStorage.getItem('user_id') || '1');
}

export default function Subscribe() {
  const navigate = useNavigate();
  const t = useT();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [paying, setPaying] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    subscriptionApi.listPlans()
      .then((res) => {
        const planList = res.data as SubscriptionPlan[];
        if (planList.length > 0) {
          setPlans(planList);
          // 默认选中推荐方案，否则第一个
          const recommended = planList.find(p => p.highlight);
          setSelectedPlanId(recommended?.id || planList[0]?.id);
        }
      })
      .catch(() => {});
  }, []);

  const selectedPlan = plans.find(p => p.id === selectedPlanId);

  const handlePay = async () => {
    if (!selectedPlanId) return;
    setPaying(true);
    try {
      const res = await subscriptionApi.subscribe(getUserId(), selectedPlanId);
      const data = res.data as { success: boolean; end_date: string; products: Array<{ product_name: string; status: string }> };
      if (data.success) {
        setSnackbar({ open: true, message: `${t.btn.subscribeSuccess} 有效期至 ${data.end_date}`, severity: 'success' });
        setTimeout(() => navigate('/app/models'), 1500);
      } else {
        setSnackbar({ open: true, message: t.btn.subscribeFail, severity: 'error' });
      }
    } catch {
      setSnackbar({ open: true, message: t.btn.payFail, severity: 'error' });
    } finally {
      setPaying(false);
    }
  };

  return (
    <Box>
      <PageHeader
        title={t.btn.subscribeNow}
        actions={<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/app/models')} sx={{ color: '#94a3b8' }}>{t.btn.back}</Button>}
      />

      <Box sx={{ maxWidth: 800, mx: 'auto' }}>
        {/* 方案选择 */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' }, gap: 2, mb: 4 }}>
          {plans.map((plan, i) => (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
            >
              <GlassPanel
                glow
                glowColor={selectedPlanId === plan.id ? '#22d3ee' : 'transparent'}
                onClick={() => setSelectedPlanId(plan.id)}
                sx={{
                  cursor: 'pointer',
                  p: 3,
                  border: selectedPlanId === plan.id ? '1px solid rgba(34,211,238,0.5)' : '1px solid rgba(148,163,184,0.1)',
                  position: 'relative',
                  transition: 'all 0.3s ease',
                  '&:hover': { borderColor: 'rgba(34,211,238,0.3)' },
                }}
              >
                {plan.highlight && (
                  <Chip icon={<StarIcon />} label="推荐" size="small" sx={{ position: 'absolute', top: 10, right: 10, backgroundColor: 'rgba(34,211,238,0.15)', color: '#22d3ee' }} />
                )}
                <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', mb: 0.5 }}>{plan.plan_name}</Typography>
                <Typography sx={{ color: '#94a3b8', fontSize: '0.8rem', mb: 1.5 }}>{plan.description}</Typography>

                <Box sx={{ mb: 1.5 }}>
                  {plan.price_monthly && (
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>¥{plan.price_monthly}/月</Typography>
                  )}
                  {plan.price_yearly && (
                    <Typography sx={{ fontWeight: 800, fontSize: '1.3rem', color: '#22d3ee' }}>
                      ¥{plan.price_yearly}<Typography component="span" sx={{ color: '#94a3b8', fontSize: '0.8rem', fontWeight: 400 }}>/年</Typography>
                    </Typography>
                  )}
                  {plan.price_unit && (
                    <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', color: '#22d3ee' }}>{plan.price_unit}</Typography>
                  )}
                </Box>

                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                  {(plan.stock_pools || []).map(sp => (
                    <Chip key={sp} label={sp} size="small" sx={{ backgroundColor: 'rgba(34,211,238,0.08)', color: '#22d3ee', fontSize: '0.65rem' }} />
                  ))}
                </Box>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {(plan.frequencies || []).map(f => (
                    <Chip key={f} label={f} size="small" variant="outlined" sx={{ borderColor: 'rgba(148,163,184,0.2)', color: '#94a3b8', fontSize: '0.65rem' }} />
                  ))}
                </Box>
              </GlassPanel>
            </motion.div>
          ))}
        </Box>

        {/* 选中方案详情 */}
        {selectedPlan && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <GlassPanel glow glowColor="#22d3ee" sx={{ p: 4 }}>
              <Typography variant="h4" sx={{
                fontWeight: 800, mb: 1,
                background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
                backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>
                {selectedPlan.plan_name}
              </Typography>
              <Typography sx={{ color: '#94a3b8', mb: 3 }}>{selectedPlan.description}</Typography>

              {/* Features */}
              <Box sx={{ mb: 3 }}>
                {(selectedPlan.features || []).map((f, i) => (
                  <Box
                    key={i}
                    component={motion.div}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.06 }}
                    sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}
                  >
                    <CheckCircleIcon sx={{ color: '#10b981', fontSize: 18 }} />
                    <Typography sx={{ color: '#e2e8f0', fontSize: '0.9rem' }}>{f}</Typography>
                  </Box>
                ))}
              </Box>

              {/* Price & Pay */}
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 3 }}>
                {selectedPlan.price_yearly && (
                  <>
                    <Typography sx={{ fontWeight: 800, fontSize: '2.5rem', color: '#22d3ee' }}>¥{selectedPlan.price_yearly}</Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '1rem' }}>/年</Typography>
                  </>
                )}
                {selectedPlan.price_unit && (
                  <Typography sx={{ fontWeight: 800, fontSize: '2rem', color: '#22d3ee' }}>{selectedPlan.price_unit}</Typography>
                )}
              </Box>

              <Button
                variant="contained"
                fullWidth
                size="large"
                onClick={handlePay}
                disabled={paying}
                sx={{
                  py: 1.5, borderRadius: 2, fontWeight: 700, fontSize: '1.1rem',
                  background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
                  '&:hover': { background: 'linear-gradient(135deg, #06b6d4, #7c3aed)' },
                }}
              >
                {paying ? t.btn.paying : selectedPlan.price_yearly ? `${t.btn.subscribe} ¥${selectedPlan.price_yearly}/年` : t.btn.contactSales}
              </Button>
            </GlassPanel>
          </motion.div>
        )}

        {plans.length === 0 && (
          <GlassPanel sx={{ p: 4, textAlign: 'center' }}>
            <Typography sx={{ color: '#94a3b8' }}>{t.btn.noPlans}</Typography>
          </GlassPanel>
        )}
      </Box>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}