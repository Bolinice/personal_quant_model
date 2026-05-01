import { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Check as CheckIcon,
  Star as StarIcon,
  WorkspacePremium as CrownIcon,
} from '@mui/icons-material';
import { subscriptionApi } from '@/api/endpoints/subscription';
import type { SubscriptionPlan, CurrentSubscription } from '@/api/types/subscription';
import { useTranslation } from 'react-i18next';

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free: null,
  basic: <StarIcon sx={{ color: '#60a5fa' }} />,
  pro: <StarIcon sx={{ color: '#a78bfa' }} />,
  enterprise: <CrownIcon sx={{ color: '#fbbf24' }} />,
};

const PLAN_COLORS: Record<string, string> = {
  free: '#64748b',
  basic: '#3b82f6',
  pro: '#8b5cf6',
  enterprise: '#f59e0b',
};

export default function SubscriptionPage() {
  const { t } = useTranslation();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [current, setCurrent] = useState<CurrentSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [subscribing, setSubscribing] = useState(false);
  const [confirmPlan, setConfirmPlan] = useState<SubscriptionPlan | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [plansRes, currentRes] = await Promise.all([
        subscriptionApi.getPlans(),
        subscriptionApi.getCurrent(1),
      ]);
      setPlans(plansRes.data?.data || []);
      setCurrent(currentRes.data?.data || null);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (plan: SubscriptionPlan) => {
    setSubscribing(true);
    try {
      await subscriptionApi.subscribe(1, plan.id);
      setConfirmPlan(null);
      await loadData();
    } catch (err: any) {
      setError(err.message || '订阅失败');
    } finally {
      setSubscribing(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  const currentPlanName = current?.subscription_plan || 'free';

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 0.5, color: '#f1f5f9', fontWeight: 700 }}>
        {t('subscription.title', '套餐与权益')}
      </Typography>
      <Typography variant="body2" sx={{ mb: 4, color: '#64748b' }}>
        {t('subscription.subtitle', '选择适合您的套餐，解锁更多量化能力')}
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
          {error}
        </Alert>
      )}

      {/* 当前订阅状态 */}
      {current && (
        <Card
          sx={{
            mb: 4,
            background: 'linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1))',
            border: '1px solid rgba(99,102,241,0.2)',
            borderRadius: 3,
          }}
        >
          <CardContent
            sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          >
            <Box>
              <Typography variant="body2" sx={{ color: '#94a3b8', mb: 0.5 }}>
                {t('subscription.currentPlan', '当前套餐')}
              </Typography>
              <Typography
                variant="h6"
                sx={{ color: '#e2e8f0', textTransform: 'capitalize', fontWeight: 700 }}
              >
                {current.plan_detail?.display_name || currentPlanName}
              </Typography>
              {current.expires_at && (
                <Typography variant="caption" sx={{ color: '#64748b' }}>
                  {t('subscription.expiresAt', '到期时间')}: {current.expires_at}
                </Typography>
              )}
            </Box>
            <Chip
              label={
                current.subscription_status === 'active'
                  ? t('subscription.active', '生效中')
                  : t('subscription.inactive', '未激活')
              }
              color={current.subscription_status === 'active' ? 'success' : 'default'}
              size="small"
            />
          </CardContent>
        </Card>
      )}

      {/* 套餐列表 */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr 1fr' },
          gap: 3,
        }}
      >
        {plans.map((plan) => {
          const isCurrent = plan.name === currentPlanName;
          const features = plan.features ? plan.features.split(',') : [];
          const color = PLAN_COLORS[plan.name] || '#64748b';

          return (
            <Card
              key={plan.id}
              sx={{
                position: 'relative',
                background: isCurrent
                  ? `linear-gradient(180deg, rgba(${hexToRgb(color)}, 0.08), rgba(15,23,42,0.95))`
                  : 'rgba(15,23,42,0.6)',
                border: isCurrent ? `1px solid ${color}` : '1px solid rgba(100,116,139,0.15)',
                borderRadius: 3,
                transition: 'all 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: `0 8px 30px rgba(${hexToRgb(color)}, 0.15)`,
                },
              }}
            >
              {isCurrent && (
                <Chip
                  label={t('subscription.current', '当前')}
                  size="small"
                  sx={{
                    position: 'absolute',
                    top: 12,
                    right: 12,
                    background: color,
                    color: '#fff',
                    fontWeight: 600,
                  }}
                />
              )}
              <CardContent sx={{ p: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  {PLAN_ICONS[plan.name]}
                  <Typography variant="h6" sx={{ fontWeight: 700, color: '#f1f5f9' }}>
                    {plan.display_name}
                  </Typography>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="h3" sx={{ fontWeight: 800, color, display: 'inline' }}>
                    ¥{plan.price}
                  </Typography>
                  {plan.price > 0 && (
                    <Typography
                      variant="body2"
                      sx={{ color: '#64748b', display: 'inline', ml: 0.5 }}
                    >
                      /
                      {plan.duration_days >= 365
                        ? t('subscription.year', '年')
                        : t('subscription.month', '月')}
                    </Typography>
                  )}
                </Box>

                <List dense sx={{ mb: 3, '& .MuiListItem-root': { px: 0, py: 0.3 } }}>
                  {features.map((f, i) => (
                    <ListItem key={i}>
                      <ListItemIcon sx={{ minWidth: 28 }}>
                        <CheckIcon sx={{ fontSize: 16, color }} />
                      </ListItemIcon>
                      <ListItemText
                        primary={f.trim()}
                        slotProps={{
                          primary: { variant: 'body2', sx: { color: '#cbd5e1' } },
                        }}
                      />
                    </ListItem>
                  ))}
                </List>

                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Chip
                    label={`${plan.max_stocks}${t('subscription.stocks', '只股票')}`}
                    size="small"
                    variant="outlined"
                    sx={{ borderColor: 'rgba(100,116,139,0.3)', color: '#94a3b8' }}
                  />
                  <Chip
                    label={`${plan.max_strategies}${t('subscription.strategies', '个策略')}`}
                    size="small"
                    variant="outlined"
                    sx={{ borderColor: 'rgba(100,116,139,0.3)', color: '#94a3b8' }}
                  />
                </Box>

                <Button
                  fullWidth
                  variant={isCurrent ? 'outlined' : 'contained'}
                  disabled={isCurrent}
                  onClick={() => setConfirmPlan(plan)}
                  sx={{
                    borderRadius: 2,
                    py: 1,
                    fontWeight: 600,
                    ...(isCurrent
                      ? { borderColor: 'rgba(100,116,139,0.3)', color: '#64748b' }
                      : {
                          background: color,
                          '&:hover': { background: color, filter: 'brightness(1.1)' },
                        }),
                  }}
                >
                  {isCurrent
                    ? t('subscription.currentPlan', '当前套餐')
                    : t('subscription.subscribe', '立即订阅')}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </Box>

      {/* 确认订阅弹窗 */}
      <Dialog
        open={!!confirmPlan}
        onClose={() => setConfirmPlan(null)}
        slotProps={{ paper: { sx: { background: '#1e293b', borderRadius: 3 } } }}
      >
        <DialogTitle sx={{ color: '#f1f5f9' }}>
          {t('subscription.confirmTitle', '确认订阅')}
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: '#cbd5e1' }}>
            {t('subscription.confirmMessage', '确认订阅 {name} 套餐？费用 ¥{price}/{period}', {
              name: confirmPlan?.display_name,
              price: confirmPlan?.price,
              period:
                confirmPlan && confirmPlan.duration_days >= 365
                  ? t('subscription.year', '年')
                  : t('subscription.month', '月'),
            })}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmPlan(null)} sx={{ color: '#94a3b8' }}>
            {t('common.cancel', '取消')}
          </Button>
          <Button
            onClick={() => confirmPlan && handleSubscribe(confirmPlan)}
            disabled={subscribing}
            variant="contained"
            sx={{ background: PLAN_COLORS[confirmPlan?.name || 'free'] }}
          >
            {subscribing ? <CircularProgress size={20} /> : t('subscription.confirm', '确认')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r},${g},${b}`;
}
