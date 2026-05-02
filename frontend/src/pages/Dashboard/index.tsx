import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button, LinearProgress, CircularProgress } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FunctionsIcon from '@mui/icons-material/Functions';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TimelineIcon from '@mui/icons-material/Timeline';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import MonitorIcon from '@mui/icons-material/Monitor';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { motion } from 'framer-motion';
import { factorApi, modelApi, monitorApi } from '@/api';
import type { Regime, MonitorAlert, MonitorFactorHealth } from '@/api';
import { PageHeader, GlassPanel, NeonChip, MetricCard } from '@/components/ui';
import { useOnboarding } from '@/contexts/OnboardingContext';

// regimeLabel：映射后端regime枚举到中文，兼容新旧两种枚举值
// mean_reverting/range_bound均映射为"震荡"，risk_on/aggressive均映射为"进攻"
const regimeLabel: Record<string, string> = {
  trending: '趋势',
  mean_reverting: '震荡',
  range_bound: '震荡',
  defensive: '防御',
  risk_on: '进攻',
  aggressive: '进攻',
};
const regimeColor: Record<string, string> = {
  trending: '#22d3ee',
  mean_reverting: '#f59e0b',
  range_bound: '#f59e0b',
  defensive: '#f43f5e',
  risk_on: '#10b981',
  aggressive: '#10b981',
};

const moduleLabel: Record<string, string> = {
  quality_growth: '质量成长',
  expectation: '修正预期',
  residual_momentum: '残差动量',
  flow_confirm: '资金确认',
};

const quickLinks = [
  {
    label: '因子管理',
    path: '/app/factors',
    icon: <FunctionsIcon sx={{ fontSize: 28 }} />,
    color: '#22d3ee',
  },
  {
    label: '模型管理',
    path: '/app/models',
    icon: <ModelTrainingIcon sx={{ fontSize: 28 }} />,
    color: '#8b5cf6',
  },
  {
    label: '回测管理',
    path: '/app/backtests',
    icon: <AssessmentIcon sx={{ fontSize: 28 }} />,
    color: '#f59e0b',
  },
  {
    label: '择时管理',
    path: '/app/timing',
    icon: <TimelineIcon sx={{ fontSize: 28 }} />,
    color: '#10b981',
  },
  {
    label: '组合管理',
    path: '/app/portfolios',
    icon: <AccountBalanceIcon sx={{ fontSize: 28 }} />,
    color: '#ec4899',
  },
  {
    label: '绩效分析',
    path: '/app/performance',
    icon: <TrendingUpIcon sx={{ fontSize: 28 }} />,
    color: '#f97316',
  },
  {
    label: '监控中心',
    path: '/app/monitor',
    icon: <MonitorIcon sx={{ fontSize: 28 }} />,
    color: '#06b6d4',
  },
  {
    label: '事件中心',
    path: '/app/events',
    icon: <NotificationsIcon sx={{ fontSize: 28 }} />,
    color: '#ef4444',
  },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { startTour, isTourCompleted } = useOnboarding();
  const [loading, setLoading] = useState(true);
  const [factorCount, setFactorCount] = useState(0);
  const [modelCount, setModelCount] = useState(0);
  const [regime, setRegime] = useState<Regime | null>(null);
  const [alerts, setAlerts] = useState<MonitorAlert[]>([]);
  const [factorHealth, setFactorHealth] = useState<MonitorFactorHealth[]>([]);

  useEffect(() => {
    Promise.all([
      factorApi
        .list({ limit: 1 })
        .then((res) => setFactorCount((res.data as any).total ?? res.data.length ?? 0))
        .catch(() => {}),
      modelApi
        .list({ limit: 1 })
        .then((res) => setModelCount((res.data as any).total ?? res.data.length ?? 0))
        .catch(() => {}),
      monitorApi
        .getRegime()
        .then((res) => setRegime(res.data))
        .catch(() => {}),
      monitorApi
        .getAlerts({ page_size: 5, resolved: false })
        .then((res) => setAlerts(res.data))
        .catch(() => {}),
      monitorApi
        .getFactorHealth()
        .then((res) => setFactorHealth(res.data))
        .catch(() => {}),
    ]).finally(() => setLoading(false));

    if (!isTourCompleted('dashboard')) {
      const timer = setTimeout(() => startTour('dashboard'), 500);
      return () => clearTimeout(timer);
    }
  }, [startTour, isTourCompleted]);

  const healthyCount = factorHealth.filter((f) => f.health_status === 'healthy').length;
  const warningCount = factorHealth.filter((f) => f.health_status === 'warning').length;
  const unhealthyCount = factorHealth.filter(
    (f) => f.health_status === 'unhealthy' || f.health_status === 'critical'
  ).length;

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress sx={{ color: '#22d3ee' }} />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="仪表盘"
        subtitle="实时监控系统状态和关键指标"
        breadcrumbs={[
          { label: '首页', path: '/' },
          { label: '仪表盘' },
        ]}
      />

      {/* 概览卡片 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              md: 'repeat(4, 1fr)',
            },
            gap: 2.5,
            mb: 3,
          }}
        >
          <MetricCard
            label="市场状态"
            value={regime ? regimeLabel[regime.regime] || regime.regime : '-'}
            color={regime ? regimeColor[regime.regime] || '#94a3b8' : '#94a3b8'}
          />
          <MetricCard label="因子数量" value={factorCount} color="#22d3ee" />
          <MetricCard label="模型数量" value={modelCount} color="#8b5cf6" />
          <MetricCard
            label="未解决告警"
            value={alerts.length}
            color={alerts.length > 0 ? '#f43f5e' : '#10b981'}
          />
        </Box>
      </motion.div>

      {/* 详细信息 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              md: 'repeat(2, 1fr)',
            },
            gap: 2.5,
          }}
        >
          {/* 市场状态详情 */}
          <GlassPanel>
            <Typography
              sx={{
                fontSize: '1.125rem',
                fontWeight: 600,
                color: '#e2e8f0',
                mb: 2,
              }}
            >
              市场状态
            </Typography>
            {regime ? (
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                  <Box
                    sx={{
                      width: 16,
                      height: 16,
                      borderRadius: '50%',
                      bgcolor: regimeColor[regime.regime] || '#94a3b8',
                      boxShadow: `0 0 12px ${regimeColor[regime.regime] || '#94a3b8'}40`,
                    }}
                  />
                  <Typography
                    sx={{
                      fontWeight: 700,
                      fontSize: '1.5rem',
                      color: regimeColor[regime.regime] || '#e2e8f0',
                    }}
                  >
                    {regimeLabel[regime.regime] || regime.regime}
                  </Typography>
                  {regime.confidence != null && (
                    <Typography sx={{ fontSize: '0.875rem', color: '#64748b' }}>
                      置信度 {(regime.confidence * 100).toFixed(0)}%
                    </Typography>
                  )}
                </Box>
                {regime.trade_date && (
                  <Typography sx={{ fontSize: '0.875rem', color: '#64748b', mb: 2 }}>
                    日期: {regime.trade_date}
                  </Typography>
                )}
                {regime.module_weight_adjustment && (
                  <Box>
                    <Typography
                      sx={{
                        fontSize: '0.8125rem',
                        color: '#64748b',
                        mb: 1,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                      }}
                    >
                      模块权重调整
                    </Typography>
                    {Object.entries(regime.module_weight_adjustment).map(([k, v]) => (
                      <Box
                        key={k}
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          py: 0.75,
                          borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
                        }}
                      >
                        <Typography sx={{ fontSize: '0.875rem', color: '#94a3b8' }}>
                          {moduleLabel[k] || k}
                        </Typography>
                        <Typography
                          sx={{
                            fontSize: '0.875rem',
                            fontFamily: '"JetBrains Mono", monospace',
                            fontWeight: 600,
                            color: '#e2e8f0',
                          }}
                        >
                          {(v as number).toFixed(2)}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            ) : (
              <Typography sx={{ color: '#64748b', fontSize: '0.9375rem' }}>
                暂无市场状态数据
              </Typography>
            )}
          </GlassPanel>

          {/* 因子健康概览 */}
          <GlassPanel>
            <Typography
              sx={{
                fontSize: '1.125rem',
                fontWeight: 600,
                color: '#e2e8f0',
                mb: 2,
              }}
            >
              因子健康概览
            </Typography>
            {factorHealth.length > 0 ? (
              <Box>
                <Box sx={{ display: 'flex', gap: 3, mb: 3 }}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography sx={{ fontSize: '2rem', fontWeight: 700, color: '#10b981', lineHeight: 1 }}>
                      {healthyCount}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748b', mt: 0.5 }}>
                      健康
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography sx={{ fontSize: '2rem', fontWeight: 700, color: '#f59e0b', lineHeight: 1 }}>
                      {warningCount}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748b', mt: 0.5 }}>
                      警告
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography sx={{ fontSize: '2rem', fontWeight: 700, color: '#f43f5e', lineHeight: 1 }}>
                      {unhealthyCount}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748b', mt: 0.5 }}>
                      异常
                    </Typography>
                  </Box>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={factorHealth.length > 0 ? (healthyCount / factorHealth.length) * 100 : 0}
                  sx={{
                    height: 8,
                    borderRadius: '4px',
                    mb: 1,
                    backgroundColor: 'rgba(148, 163, 184, 0.1)',
                    '& .MuiLinearProgress-bar': {
                      background: 'linear-gradient(90deg, #10b981 0%, #22d3ee 100%)',
                      borderRadius: '4px',
                    },
                  }}
                />
                <Typography sx={{ fontSize: '0.8125rem', color: '#64748b' }}>
                  健康率{' '}
                  {factorHealth.length > 0
                    ? ((healthyCount / factorHealth.length) * 100).toFixed(0)
                    : 0}
                  %
                </Typography>
              </Box>
            ) : (
              <Typography sx={{ color: '#64748b', fontSize: '0.9375rem' }}>
                暂无因子健康数据
              </Typography>
            )}
          </GlassPanel>

          {/* 最新告警 */}
          <GlassPanel>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 2,
              }}
            >
              <Typography
                sx={{
                  fontSize: '1.125rem',
                  fontWeight: 600,
                  color: '#e2e8f0',
                }}
              >
                最新告警
              </Typography>
              <Button
                size="small"
                endIcon={<ArrowForwardIcon />}
                onClick={() => navigate('/app/monitor')}
                sx={{
                  color: '#22d3ee',
                  textTransform: 'none',
                  fontSize: '0.8125rem',
                  '&:hover': {
                    backgroundColor: 'rgba(34, 211, 238, 0.1)',
                  },
                }}
              >
                查看全部
              </Button>
            </Box>
            {alerts.length > 0 ? (
              <Box>
                {alerts.map((a) => (
                  <Box
                    key={a.alert_id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1.5,
                      py: 1,
                      borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
                      '&:last-child': {
                        borderBottom: 'none',
                      },
                    }}
                  >
                    <NeonChip
                      label={
                        a.severity === 'critical'
                          ? '严重'
                          : a.severity === 'warning'
                            ? '警告'
                            : '信息'
                      }
                      size="small"
                      neonColor={
                        a.severity === 'critical'
                          ? 'red'
                          : a.severity === 'warning'
                            ? 'amber'
                            : 'default'
                      }
                    />
                    <Typography
                      sx={{
                        flex: 1,
                        fontSize: '0.875rem',
                        color: '#e2e8f0',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {a.message || a.object_name || '-'}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: '0.75rem',
                        color: '#64748b',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {a.alert_time?.slice(5, 16).replace('T', ' ')}
                    </Typography>
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography sx={{ color: '#64748b', fontSize: '0.9375rem' }}>暂无告警</Typography>
            )}
          </GlassPanel>

          {/* 快捷入口 */}
          <GlassPanel data-tour="quick-links">
            <Typography
              sx={{
                fontSize: '1.125rem',
                fontWeight: 600,
                color: '#e2e8f0',
                mb: 2,
              }}
            >
              快捷入口
            </Typography>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 1.5,
              }}
            >
              {quickLinks.map((link) => (
                <Box
                  key={link.path}
                  onClick={() => navigate(link.path)}
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 0.75,
                    p: 2,
                    borderRadius: '12px',
                    cursor: 'pointer',
                    border: '1px solid rgba(148, 163, 184, 0.06)',
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      backgroundColor: 'rgba(148, 163, 184, 0.06)',
                      borderColor: `${link.color}40`,
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  <Box sx={{ color: link.color }}>{link.icon}</Box>
                  <Typography
                    sx={{
                      fontSize: '0.75rem',
                      color: '#94a3b8',
                      textAlign: 'center',
                    }}
                  >
                    {link.label}
                  </Typography>
                </Box>
              ))}
            </Box>
          </GlassPanel>
        </Box>
      </motion.div>
    </Box>
  );
}
