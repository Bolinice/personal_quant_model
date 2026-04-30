import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Chip,
} from '@mui/material';
import { motion } from 'framer-motion';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import LockIcon from '@mui/icons-material/Lock';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import { PageHeader, GlassPanel, NeonChip, GlassTable } from '@/components/ui';
import { subscriptionApi } from '@/api';
import type { SubscriptionPlan } from '@/api';
import { useLang } from '@/i18n';

function getUserId(): number {
  return Number(localStorage.getItem('user_id') || '1');
}

const COMPARISON = [
  {
    feature: '股票池',
    free: '沪深300/中证500',
    basic: '沪深300/中证500',
    pro: '全部股票池',
    team: '全部股票池',
  },
  {
    feature: '调仓频率',
    free: '月频',
    basic: '周频',
    pro: '日频/周频/月频',
    team: '日频/周频/月频',
  },
  { feature: '模型数量', free: '2', basic: '5', pro: '20', team: '无限' },
  { feature: '回测次数/月', free: '3', basic: '10', pro: '50', team: '无限' },
  { feature: '数据导出', free: 'CSV', basic: 'CSV/Excel', pro: 'CSV/Excel/JSON', team: '全格式' },
  { feature: 'API 接入', free: '—', basic: '—', pro: '✓', team: '✓' },
  { feature: '团队协作', free: '—', basic: '—', pro: '—', team: '✓' },
  { feature: '深度分析', free: '—', basic: '—', pro: '✓', team: '✓' },
];

const TIER_MAP: Record<string, string> = {
  free: '免费版',
  basic: '基础版',
  pro: '专业版',
  team: '团队版',
};

const TIER_INDEX: Record<string, number> = {
  free: 0,
  basic: 1,
  pro: 2,
  team: 3,
};

const BENEFIT_KEYS = [
  'availablePools',
  'availableFreq',
  'modelCount',
  'dataPermission',
  'apiPermission',
  'collabPermission',
] as const;

export default function ModelPlan() {
  const navigate = useNavigate();
  const { t } = useLang();
  const [currentPlan, setCurrentPlan] = useState<SubscriptionPlan | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [expireDate, setExpireDate] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([subscriptionApi.getMySubscriptions(getUserId()), subscriptionApi.listPlans()])
      .then(([subRes, plansRes]) => {
        const planList = plansRes.data as SubscriptionPlan[];
        setPlans(planList);

        const subs = subRes.data as Array<{ plan_id: number; end_date: string; status: string }>;
        const activeSub = Array.isArray(subs) ? subs.find((s) => s.status === 'active') : null;
        if (activeSub) {
          setExpireDate(activeSub.end_date);
          const matched = planList.find((p) => p.id === activeSub.plan_id);
          if (matched) setCurrentPlan(matched);
        }
        // If no active subscription, default to free tier
        if (!activeSub && planList.length > 0) {
          const freePlan = planList.find((p) => p.plan_tier === 0) || planList[0];
          setCurrentPlan(freePlan);
        }
      })
      .catch(() => setError('加载套餐信息失败'))
      .finally(() => setLoading(false));
  }, []);

  // Determine the tier key for the current plan
  const currentTier = currentPlan?.plan_type || 'free';
  const currentTierIdx = TIER_INDEX[currentTier] ?? 0;

  // Compute benefit availability based on plan tier
  const benefits = BENEFIT_KEYS.map((key) => {
    let available = false;
    switch (key) {
      case 'availablePools':
        available = currentTierIdx >= 2; // pro+
        break;
      case 'availableFreq':
        available = currentTierIdx >= 1; // basic+
        break;
      case 'modelCount':
        available = true; // always has some
        break;
      case 'dataPermission':
        available = currentTierIdx >= 1;
        break;
      case 'apiPermission':
        available = currentTierIdx >= 2;
        break;
      case 'collabPermission':
        available = currentTierIdx >= 3;
        break;
    }
    return { key, available };
  });

  // Determine recommended upgrade plan
  const recommendedTier = currentTierIdx < 2 ? 'pro' : currentTierIdx < 3 ? 'team' : null;
  const recommendedPlan = recommendedTier
    ? plans.find((p) => p.plan_type === recommendedTier)
    : null;

  const upgradeFeatures: string[] = [];
  if (currentTierIdx < 2) {
    upgradeFeatures.push(
      '全部股票池',
      '日频/周频/月频',
      '20 个模型',
      '50 次回测/月',
      'API 接入',
      '深度分析'
    );
  } else if (currentTierIdx < 3) {
    upgradeFeatures.push('无限模型', '无限回测', '全格式导出', '团队协作');
  }

  if (loading) {
    return (
      <Box>
        <PageHeader title={t.models.plan} />
        <GlassPanel sx={{ p: 4, textAlign: 'center' }}>
          <Typography sx={{ color: '#94a3b8' }}>加载中...</Typography>
        </GlassPanel>
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <PageHeader title={t.models.plan} />
        <GlassPanel sx={{ p: 4, textAlign: 'center' }}>
          <Typography sx={{ color: '#f43f5e' }}>{error}</Typography>
        </GlassPanel>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title={t.models.plan} />

      {/* Current Plan Card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Box
          sx={{
            position: 'relative',
            borderRadius: 3,
            p: '2px',
            background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
            mb: 3,
          }}
        >
          <GlassPanel
            glow
            glowColor="#22d3ee"
            animate={false}
            sx={{
              p: 3,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 2,
            }}
          >
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                <Typography
                  variant="h4"
                  sx={{
                    fontWeight: 800,
                    background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
                    backgroundClip: 'text',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                  }}
                >
                  {currentPlan?.plan_name || TIER_MAP[currentTier] || '免费版'}
                </Typography>
                <NeonChip label={t.models.currentPlan} neonColor="cyan" />
              </Box>
              {expireDate && (
                <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                  {t.models.expireDate}：{expireDate}
                </Typography>
              )}
            </Box>
            <Box sx={{ textAlign: 'right' }}>
              <Typography sx={{ fontWeight: 800, fontSize: '2rem', color: '#22d3ee' }}>
                {currentPlan?.price_yearly
                  ? `¥${currentPlan.price_yearly}`
                  : currentPlan?.price_monthly
                    ? `¥${currentPlan.price_monthly}`
                    : '免费'}
              </Typography>
              {currentPlan?.price_yearly && (
                <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                  /年
                </Typography>
              )}
              {currentPlan?.price_monthly && !currentPlan?.price_yearly && (
                <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                  /月
                </Typography>
              )}
            </Box>
          </GlassPanel>
        </Box>
      </motion.div>

      {/* 权益总览 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
      >
        <GlassPanel sx={{ mb: 3 }}>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 700,
              mb: 2,
              color: '#e2e8f0',
            }}
          >
            {t.models.currentPlan}
          </Typography>
          <Grid container spacing={1.5}>
            {benefits.map(({ key, available }) => (
              <Grid size={{ xs: 12, sm: 6 }} key={key}>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    p: 1.5,
                    borderRadius: 2,
                    backgroundColor: available
                      ? 'rgba(16, 185, 129, 0.06)'
                      : 'rgba(148, 163, 184, 0.04)',
                    border: `1px solid ${available ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.08)'}`,
                  }}
                >
                  {available ? (
                    <CheckCircleIcon sx={{ color: '#10b981', fontSize: 20 }} />
                  ) : (
                    <CancelIcon sx={{ color: '#64748b', fontSize: 20 }} />
                  )}
                  <Typography
                    sx={{
                      color: available ? '#e2e8f0' : '#64748b',
                      fontSize: '0.9rem',
                      fontWeight: available ? 500 : 400,
                    }}
                  >
                    {t.models[key as keyof typeof t.models]}
                  </Typography>
                  {!available && (
                    <Chip
                      icon={<LockIcon sx={{ fontSize: '0.7rem !important' }} />}
                      label={t.models.locked}
                      size="small"
                      sx={{
                        ml: 'auto',
                        backgroundColor: 'rgba(148, 163, 184, 0.08)',
                        color: '#94a3b8',
                        fontSize: '0.65rem',
                        height: 22,
                        '& .MuiChip-icon': { color: '#94a3b8' },
                      }}
                    />
                  )}
                </Box>
              </Grid>
            ))}
          </Grid>
        </GlassPanel>
      </motion.div>

      {/* Comparison Matrix */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <Typography
          variant="h6"
          sx={{
            fontWeight: 700,
            mb: 2,
            color: '#e2e8f0',
          }}
        >
          {t.models.planComparison}
        </Typography>
        <GlassTable>
          <TableHead>
            <TableRow>
              <TableCell
                sx={{
                  color: '#94a3b8',
                  fontWeight: 700,
                  borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                }}
              >
                功能
              </TableCell>
              {['免费版', '基础版', '专业版', '团队版'].map((col, i) => (
                <TableCell
                  key={col}
                  align="center"
                  sx={{
                    color: i === currentTierIdx ? '#22d3ee' : '#94a3b8',
                    fontWeight: i === currentTierIdx ? 800 : 700,
                    borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                    ...(i === currentTierIdx && {
                      background: 'rgba(34, 211, 238, 0.06)',
                    }),
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 0.5,
                    }}
                  >
                    {col}
                    {i === currentTierIdx && (
                      <NeonChip label={t.models.currentPlan} neonColor="cyan" size="small" />
                    )}
                  </Box>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {COMPARISON.map((row) => (
              <TableRow
                key={row.feature}
                sx={{
                  '&:last-child td': { borderBottom: 0 },
                  '& td': { borderBottom: '1px solid rgba(148, 163, 184, 0.06)' },
                }}
              >
                <TableCell sx={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.85rem' }}>
                  {row.feature}
                </TableCell>
                {[row.free, row.basic, row.pro, row.team].map((val, i) => (
                  <TableCell
                    key={i}
                    align="center"
                    sx={{
                      color: val === '—' ? '#475569' : i === currentTierIdx ? '#e2e8f0' : '#94a3b8',
                      fontWeight: i === currentTierIdx ? 600 : 400,
                      fontSize: '0.85rem',
                      ...(i === currentTierIdx && {
                        background: 'rgba(34, 211, 238, 0.04)',
                      }),
                    }}
                  >
                    {val === '—' ? (
                      <CancelIcon sx={{ fontSize: 16, color: '#475569' }} />
                    ) : val === '✓' ? (
                      <CheckCircleIcon
                        sx={{ fontSize: 18, color: i >= currentTierIdx ? '#10b981' : '#475569' }}
                      />
                    ) : (
                      val
                    )}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </GlassTable>
      </motion.div>

      {/* Upgrade Recommendation */}
      {recommendedPlan && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Box sx={{ mt: 3 }}>
            <GlassPanel
              glow
              glowColor="#8b5cf6"
              sx={{
                p: 3,
                background:
                  'linear-gradient(135deg, rgba(15, 23, 42, 0.8), rgba(139, 92, 246, 0.08))',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <ArrowUpwardIcon sx={{ color: '#8b5cf6' }} />
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 700,
                    color: '#e2e8f0',
                  }}
                >
                  {t.models.recommendUpgrade}：
                  {TIER_MAP[recommendedTier!] || recommendedPlan.plan_name}
                </Typography>
              </Box>

              <Typography variant="body2" sx={{ color: '#94a3b8', mb: 2 }}>
                {t.models.unlockFeatures}
              </Typography>

              <Box sx={{ mb: 3 }}>
                {upgradeFeatures.map((feat, i) => (
                  <Box
                    key={i}
                    component={motion.div}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.06 }}
                    sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.75 }}
                  >
                    <LockIcon sx={{ color: '#8b5cf6', fontSize: 16 }} />
                    <Typography sx={{ color: '#e2e8f0', fontSize: '0.9rem' }}>{feat}</Typography>
                  </Box>
                ))}
              </Box>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<ArrowUpwardIcon />}
                  onClick={() => navigate('/subscribe')}
                  sx={{
                    py: 1.2,
                    px: 4,
                    borderRadius: 2,
                    fontWeight: 700,
                    fontSize: '1rem',
                    background: 'linear-gradient(135deg, #8b5cf6, #22d3ee)',
                    '&:hover': {
                      background: 'linear-gradient(135deg, #7c3aed, #06b6d4)',
                    },
                  }}
                >
                  {t.models.upgradeNow}
                </Button>
                {recommendedPlan.price_yearly && (
                  <Typography sx={{ color: '#94a3b8', fontSize: '0.9rem' }}>
                    ¥{recommendedPlan.price_yearly}/年
                  </Typography>
                )}
              </Box>
            </GlassPanel>
          </Box>
        </motion.div>
      )}

      {/* Already at top tier */}
      {!recommendedPlan && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Box sx={{ mt: 3 }}>
            <GlassPanel sx={{ p: 3, textAlign: 'center' }}>
              <CheckCircleIcon sx={{ fontSize: 40, color: '#10b981', mb: 1 }} />
              <Typography sx={{ fontWeight: 700, color: '#e2e8f0', mb: 0.5 }}>
                {t.models.currentPlan}：{currentPlan?.plan_name || TIER_MAP[currentTier]}
              </Typography>
              <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                {t.models.unlockUpgrade}
              </Typography>
            </GlassPanel>
          </Box>
        </motion.div>
      )}
    </Box>
  );
}
