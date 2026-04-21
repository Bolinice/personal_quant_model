import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Grid, Typography, Button, Chip, LinearProgress, Snackbar, Alert } from '@mui/material';
import { motion } from 'framer-motion';
import AddIcon from '@mui/icons-material/Add';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import AssessmentIcon from '@mui/icons-material/Assessment';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import UpgradeIcon from '@mui/icons-material/Upgrade';
import Inventory2Icon from '@mui/icons-material/Inventory2';
import SpeedIcon from '@mui/icons-material/Speed';
import StorageIcon from '@mui/icons-material/Storage';
import ApiIcon from '@mui/icons-material/Api';
import GroupIcon from '@mui/icons-material/Group';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { PageHeader, GlassPanel, MetricCard, NeonChip } from '@/components/ui';
import { modelApi, subscriptionApi, stockPoolApi } from '@/api';
import type { Model, SubscriptionPlan, StockPool } from '@/api';
import { useLang } from '@/i18n';

function getUserId(): number {
  return Number(localStorage.getItem('user_id') || '1');
}

const POOL_NEON: Record<string, 'cyan' | 'purple' | 'green' | 'amber'> = {
  HS300: 'cyan', ZZ500: 'purple', ZZ1000: 'green', ALL_A: 'amber',
};

const fmt = (v: number | null | undefined, pct = false) => {
  if (v == null) return '-';
  return pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(4);
};

// Fallback data when APIs are unavailable
const FALLBACK_PLAN: SubscriptionPlan = {
  id: 0,
  plan_name: '免费版',
  plan_type: 'free',
  plan_tier: 0,
  price_monthly: null,
  price_yearly: null,
  price_unit: null,
  custom_price: null,
  stock_pools: ['HS300', 'ZZ500'],
  frequencies: ['daily'],
  features: ['基础因子库', '日线频率'],
  description: '免费版套餐',
  highlight: false,
  buttons: null,
  is_active: true,
};

interface PlanMetrics {
  poolCount: number;
  freqCount: number;
  dataPerm: string;
  apiPerm: string;
  collabPerm: string;
  modelCount: number;
}

function getPlanMetrics(plan: SubscriptionPlan | null, models: Model[], pools: StockPool[]): PlanMetrics {
  const tier = plan?.plan_tier ?? 0;
  const poolCodes = plan?.stock_pools ?? FALLBACK_PLAN.stock_pools ?? [];
  const freqs = plan?.frequencies ?? FALLBACK_PLAN.frequencies ?? [];

  return {
    poolCount: pools.length || poolCodes.length || 2,
    freqCount: freqs.length || 1,
    dataPerm: tier >= 2 ? '全量' : tier >= 1 ? '标准' : '基础',
    apiPerm: tier >= 2 ? '完整' : tier >= 1 ? '只读' : '无',
    collabPerm: tier >= 3 ? '团队' : tier >= 2 ? '只读' : '无',
    modelCount: models.length,
  };
}

export default function ModelOverview() {
  const navigate = useNavigate();
  const { t } = useLang();

  const [plan, setPlan] = useState<SubscriptionPlan | null>(null);
  const [subscriptionEnd, setSubscriptionEnd] = useState<string>('');
  const [models, setModels] = useState<Model[]>([]);
  const [pools, setPools] = useState<StockPool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [subsRes, modelsRes, poolsRes] = await Promise.allSettled([
          subscriptionApi.getMySubscriptions(getUserId()),
          modelApi.list({ limit: 5 }),
          stockPoolApi.list({ limit: 200 }),
        ]);

        // Subscription / plan
        if (subsRes.status === 'fulfilled') {
          const subsData = subsRes.value.data;
          const subsList = Array.isArray(subsData) ? subsData : [];
          if (subsList.length > 0) {
            const latest = subsList[0];
            setSubscriptionEnd(latest.end_date || '');
            // Try to find plan info from listPlans
            try {
              const plansRes = await subscriptionApi.listPlans();
              const plansList = plansRes.data as SubscriptionPlan[];
              const matched = plansList.find((p) => p.id === latest.plan_id);
              setPlan(matched || null);
            } catch {
              setPlan(FALLBACK_PLAN);
            }
          } else {
            setPlan(FALLBACK_PLAN);
          }
        } else {
          setPlan(FALLBACK_PLAN);
        }

        // Models
        if (modelsRes.status === 'fulfilled') {
          setModels(modelsRes.value.data);
        }

        // Pools
        if (poolsRes.status === 'fulfilled') {
          setPools(poolsRes.value.data.filter((p: StockPool) => p.is_active));
        }
      } catch {
        setError('加载数据失败');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const metrics = getPlanMetrics(plan, models, pools);
  const planName = plan?.plan_name || FALLBACK_PLAN.plan_name;

  const equityCards = [
    { label: t.models.availablePools, value: metrics.poolCount, color: '#22d3ee', icon: <Inventory2Icon /> },
    { label: t.models.availableFreq, value: metrics.freqCount, color: '#8b5cf6', icon: <SpeedIcon /> },
    { label: t.models.dataPermission, value: metrics.dataPerm, color: '#10b981', icon: <StorageIcon /> },
    { label: t.models.apiPermission, value: metrics.apiPerm, color: '#f59e0b', icon: <ApiIcon /> },
    { label: t.models.collabPermission, value: metrics.collabPerm, color: '#f43f5e', icon: <GroupIcon /> },
    { label: t.models.modelCount, value: metrics.modelCount, color: '#22d3ee', icon: <ModelTrainingIcon /> },
  ];

  const usageItems = [
    { label: t.models.monthlyBacktests, value: 12, max: plan?.plan_tier && plan.plan_tier >= 2 ? 100 : 30 },
    { label: t.models.recentModels, value: Math.min(models.length, 5), max: 5 },
    { label: t.models.recentRebalances, value: 3, max: plan?.plan_tier && plan.plan_tier >= 1 ? 50 : 10 },
    { label: t.models.recentExports, value: 2, max: plan?.plan_tier && plan.plan_tier >= 2 ? 30 : 5 },
  ];

  const quickActions = [
    { label: t.models.createModel, icon: <AddIcon />, color: '#22d3ee', path: '/app/models' },
    { label: t.models.viewTemplates, icon: <ViewModuleIcon />, color: '#8b5cf6', path: '/app/models' },
    { label: t.models.viewBacktests, icon: <AssessmentIcon />, color: '#10b981', path: '/app/backtests' },
    { label: t.models.dataExport, icon: <FileDownloadIcon />, color: '#f59e0b', path: '/app/models' },
    { label: t.models.viewUpgrade, icon: <UpgradeIcon />, color: '#f43f5e', path: '/app/subscribe' },
  ];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <Typography sx={{ color: '#94a3b8' }}>加载中...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title={t.models.overview}
        subtitle={t.models.plan}
      />

      {/* ── Top status bar: plan info ── */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <GlassPanel glow glowColor="#22d3ee" sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <NeonChip label={t.models.currentPlan} neonColor="cyan" size="small" />
            <Typography sx={{ fontWeight: 700, color: '#e2e8f0', fontSize: '1.1rem' }}>
              {planName}
            </Typography>
            {subscriptionEnd && (
              <>
                <Typography sx={{ color: '#64748b', fontSize: '0.85rem' }}>{t.models.expireDate}</Typography>
                <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600 }}>
                  {subscriptionEnd.slice(0, 10)}
                </Typography>
              </>
            )}
          </Box>
          <Button
            variant="outlined"
            size="small"
            startIcon={<UpgradeIcon />}
            onClick={() => navigate('/app/subscribe')}
            sx={{
              borderColor: 'rgba(34, 211, 238, 0.4)',
              color: '#22d3ee',
              '&:hover': {
                borderColor: '#22d3ee',
                backgroundColor: 'rgba(34, 211, 238, 0.08)',
              },
            }}
          >
            {t.models.upgrade}
          </Button>
        </GlassPanel>
      </motion.div>

      {/* ── Equity summary cards ── */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {equityCards.map((card, i) => (
          <Grid size={{ xs: 6, sm: 4, md: 2 }} key={card.label}>
            <MetricCard
              label={card.label}
              value={card.value}
              color={card.color}
              icon={card.icon}
              delay={i * 0.08}
            />
          </Grid>
        ))}
      </Grid>

      {/* ── Usage section ── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        <GlassPanel sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, color: '#e2e8f0', mb: 2, fontSize: '1rem' }}>
            使用情况
          </Typography>
          <Grid container spacing={3}>
            {usageItems.map((item) => {
              const pct = Math.min((item.value / item.max) * 100, 100);
              const barColor = pct >= 90 ? '#f43f5e' : pct >= 70 ? '#f59e0b' : '#10b981';
              return (
                <Grid size={{ xs: 12, sm: 6, md: 3 }} key={item.label}>
                  <Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.8rem' }}>{item.label}</Typography>
                      <Typography sx={{ color: '#e2e8f0', fontSize: '0.8rem', fontWeight: 600 }}>
                        {item.value}/{item.max}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={pct}
                      sx={{
                        height: 6,
                        borderRadius: 3,
                        backgroundColor: 'rgba(148, 163, 184, 0.1)',
                        '& .MuiLinearProgress-bar': {
                          borderRadius: 3,
                          backgroundColor: barColor,
                        },
                      }}
                    />
                  </Box>
                </Grid>
              );
            })}
          </Grid>
        </GlassPanel>
      </motion.div>

      {/* ── Quick actions ── */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {quickActions.map((action, i) => (
          <Grid size={{ xs: 12, sm: 6, md: 2.4 }} key={action.label}>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.3 + i * 0.06 }}
            >
              <GlassPanel
                glow
                glowColor={action.color}
                animate={false}
                onClick={() => navigate(action.path)}
                sx={{
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 1,
                  py: 2,
                  transition: 'all 0.3s ease',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: `0 0 24px ${action.color}15`,
                  },
                }}
              >
                <Box sx={{ color: action.color, '& .MuiSvgIcon-root': { fontSize: 28 } }}>
                  {action.icon}
                </Box>
                <Typography sx={{ color: '#e2e8f0', fontSize: '0.85rem', fontWeight: 600, textAlign: 'center' }}>
                  {action.label}
                </Typography>
              </GlassPanel>
            </motion.div>
          </Grid>
        ))}
      </Grid>

      {/* ── Recent models list ── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.5 }}
      >
        <GlassPanel sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, color: '#e2e8f0', fontSize: '1rem' }}>
              {t.models.recentModels}
            </Typography>
            <Button
              size="small"
              endIcon={<ArrowForwardIcon />}
              onClick={() => navigate('/app/models')}
              sx={{ color: '#94a3b8', '&:hover': { color: '#22d3ee' } }}
            >
              {t.models.myModels}
            </Button>
          </Box>

          {models.length === 0 ? (
            <Typography sx={{ textAlign: 'center', color: '#64748b', py: 3 }}>
              暂无模型，点击「{t.models.createModel}」开始创建
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {models.map((model, i) => {
                // Derive pool code from model_code for chip display
                const poolCode = model.model_code?.split('_')[0]?.toUpperCase() || '';
                const neonColor = POOL_NEON[poolCode] || 'default';
                const ic = model.ic_mean;
                const icIr = model.ic_ir;

                return (
                  <motion.div
                    key={model.id}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: 0.6 + i * 0.06 }}
                  >
                    <Box
                      onClick={() => navigate(`/models/${poolCode || model.model_code}`)}
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        p: 1.5,
                        borderRadius: 2,
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        backgroundColor: 'transparent',
                        '&:hover': {
                          backgroundColor: 'rgba(148, 163, 184, 0.05)',
                        },
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
                        <Typography
                          sx={{
                            fontWeight: 600,
                            color: '#e2e8f0',
                            fontSize: '0.9rem',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {model.model_name}
                        </Typography>
                        <NeonChip label={poolCode || model.model_type} size="small" neonColor={neonColor} />
                        {model.status === 'active' && (
                          <Chip
                            label={t.models.running}
                            size="small"
                            sx={{
                              backgroundColor: 'rgba(16, 185, 129, 0.12)',
                              border: '1px solid rgba(16, 185, 129, 0.3)',
                              color: '#10b981',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              height: 22,
                            }}
                          />
                        )}
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, flexShrink: 0 }}>
                        <Box sx={{ textAlign: 'right' }}>
                          <Typography sx={{ color: '#64748b', fontSize: '0.7rem' }}>{t.models.annualReturn}</Typography>
                          <Typography sx={{ color: ic != null && ic >= 0 ? '#10b981' : '#f43f5e', fontSize: '0.85rem', fontWeight: 600 }}>
                            {ic != null ? fmt(ic, true) : '-'}
                          </Typography>
                        </Box>
                        <Box sx={{ textAlign: 'right' }}>
                          <Typography sx={{ color: '#64748b', fontSize: '0.7rem' }}>{t.models.sharpe}</Typography>
                          <Typography sx={{ color: '#8b5cf6', fontSize: '0.85rem', fontWeight: 600 }}>
                            {icIr != null ? fmt(icIr) : '-'}
                          </Typography>
                        </Box>
                        <ArrowForwardIcon sx={{ color: '#475569', fontSize: 18 }} />
                      </Box>
                    </Box>
                  </motion.div>
                );
              })}
            </Box>
          )}
        </GlassPanel>
      </motion.div>

      {/* ── Upgrade recommendation bar ── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.7 }}
      >
        <GlassPanel
          glow
          glowColor="#8b5cf6"
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 2,
            background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(34, 211, 238, 0.05) 100%)',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <AutoAwesomeIcon sx={{ color: '#8b5cf6' }} />
            <Box>
              <Typography sx={{ fontWeight: 600, color: '#e2e8f0', fontSize: '0.95rem' }}>
                {t.models.recommendUpgrade}
              </Typography>
              <Typography sx={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                {t.models.unlockFeatures}
              </Typography>
            </Box>
          </Box>
          <Button
            variant="contained"
            size="small"
            endIcon={<UpgradeIcon />}
            onClick={() => navigate('/app/subscribe')}
            sx={{
              background: 'linear-gradient(135deg, #8b5cf6, #22d3ee)',
              fontWeight: 600,
              borderRadius: 2,
              '&:hover': {
                background: 'linear-gradient(135deg, #7c3aed, #06b6d4)',
              },
            }}
          >
            {t.models.upgradeNow}
          </Button>
        </GlassPanel>
      </motion.div>

      <Snackbar open={!!error} autoHideDuration={3000} onClose={() => setError('')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
    </Box>
  );
}
