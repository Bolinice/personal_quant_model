import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Grid, Button, Chip, LinearProgress,
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FunctionsIcon from '@mui/icons-material/Functions';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TimelineIcon from '@mui/icons-material/Timeline';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import MonitorIcon from '@mui/icons-material/Monitor';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { factorApi, modelApi, monitorApi } from '@/api';
import type { Regime, MonitorAlert, MonitorFactorHealth } from '@/api';
import { PageHeader, GlassPanel, NeonChip, MetricCard } from '@/components/ui';

const regimeLabel: Record<string, string> = {
  trending: '趋势', mean_reverting: '震荡', range_bound: '震荡', defensive: '防御', risk_on: '进攻', aggressive: '进攻',
};
const regimeColor: Record<string, string> = {
  trending: '#22d3ee', mean_reverting: '#f59e0b', range_bound: '#f59e0b', defensive: '#f43f5e', risk_on: '#10b981', aggressive: '#10b981',
};

const moduleLabel: Record<string, string> = {
  quality_growth: '质量成长', expectation: '修正预期', residual_momentum: '残差动量', flow_confirm: '资金确认',
};

const quickLinks = [
  { label: '因子管理', path: '/app/factors', icon: <FunctionsIcon sx={{ fontSize: 28 }} />, color: '#22d3ee' },
  { label: '模型管理', path: '/app/models', icon: <ModelTrainingIcon sx={{ fontSize: 28 }} />, color: '#8b5cf6' },
  { label: '回测管理', path: '/app/backtests', icon: <AssessmentIcon sx={{ fontSize: 28 }} />, color: '#f59e0b' },
  { label: '择时管理', path: '/app/timing', icon: <TimelineIcon sx={{ fontSize: 28 }} />, color: '#10b981' },
  { label: '组合管理', path: '/app/portfolios', icon: <AccountBalanceIcon sx={{ fontSize: 28 }} />, color: '#ec4899' },
  { label: '绩效分析', path: '/app/performance', icon: <TrendingUpIcon sx={{ fontSize: 28 }} />, color: '#f97316' },
  { label: '监控中心', path: '/app/monitor', icon: <MonitorIcon sx={{ fontSize: 28 }} />, color: '#06b6d4' },
  { label: '事件中心', path: '/app/events', icon: <NotificationsIcon sx={{ fontSize: 28 }} />, color: '#ef4444' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [factorCount, setFactorCount] = useState(0);
  const [modelCount, setModelCount] = useState(0);
  const [regime, setRegime] = useState<Regime | null>(null);
  const [alerts, setAlerts] = useState<MonitorAlert[]>([]);
  const [factorHealth, setFactorHealth] = useState<MonitorFactorHealth[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      factorApi.list({ limit: 1 }).then((res) => setFactorCount(res.data.total ?? res.data.length ?? 0)).catch(() => {}),
      modelApi.list({ limit: 1 }).then((res) => setModelCount(res.data.total ?? res.data.length ?? 0)).catch(() => {}),
      monitorApi.getRegime().then((res) => setRegime(res.data)).catch(() => {}),
      monitorApi.getAlerts({ page_size: 5, resolved: false }).then((res) => setAlerts(res.data)).catch(() => {}),
      monitorApi.getFactorHealth().then((res) => setFactorHealth(res.data)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const healthyCount = factorHealth.filter((f) => f.health_status === 'healthy').length;
  const warningCount = factorHealth.filter((f) => f.health_status === 'warning').length;
  const unhealthyCount = factorHealth.filter((f) => f.health_status === 'unhealthy').length;

  return (
    <Box>
      <PageHeader title="仪表盘" />

      {/* Summary cards */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard label="市场状态" value={regime ? regimeLabel[regime.regime] || regime.regime : '-'} color={regime ? regimeColor[regime.regime] || '#94a3b8' : '#94a3b8'} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard label="因子数量" value={factorCount} color="#22d3ee" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard label="模型数量" value={modelCount} color="#8b5cf6" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard label="未解决告警" value={alerts.length} color={alerts.length > 0 ? '#f43f5e' : '#10b981'} />
        </Grid>
      </Grid>

      <Grid container spacing={2.5}>
        {/* Regime detail */}
        <Grid size={{ xs: 12, md: 6 }}>
          <GlassPanel animate={false} sx={{ height: '100%' }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>市场状态</Typography>
            {regime ? (
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                  <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: regimeColor[regime.regime] || '#94a3b8' }} />
                  <Typography sx={{ fontWeight: 700, fontSize: '1.5rem', color: regimeColor[regime.regime] || '#e2e8f0' }}>
                    {regimeLabel[regime.regime] || regime.regime}
                  </Typography>
                  {regime.confidence != null && (
                    <Typography variant="body2" sx={{ color: '#64748b' }}>
                      置信度 {(regime.confidence * 100).toFixed(0)}%
                    </Typography>
                  )}
                </Box>
                {regime.trade_date && (
                  <Typography variant="body2" sx={{ color: '#64748b', mb: 1 }}>日期: {regime.trade_date}</Typography>
                )}
                {regime.module_weight_adjustment && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" sx={{ color: '#64748b', mb: 0.5 }}>模块权重调整</Typography>
                    {Object.entries(regime.module_weight_adjustment).map(([k, v]) => (
                      <Box key={k} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2" sx={{ color: '#94a3b8' }}>{moduleLabel[k] || k}</Typography>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', color: '#e2e8f0' }}>{(v as number).toFixed(2)}</Typography>
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            ) : (
              <Typography sx={{ color: '#64748b' }}>暂无市场状态数据</Typography>
            )}
          </GlassPanel>
        </Grid>

        {/* Factor health summary */}
        <Grid size={{ xs: 12, md: 6 }}>
          <GlassPanel animate={false} sx={{ height: '100%' }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>因子健康概览</Typography>
            {factorHealth.length > 0 ? (
              <Box>
                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography sx={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981' }}>{healthyCount}</Typography>
                    <Typography variant="caption" sx={{ color: '#64748b' }}>健康</Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography sx={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b' }}>{warningCount}</Typography>
                    <Typography variant="caption" sx={{ color: '#64748b' }}>警告</Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography sx={{ fontSize: '1.5rem', fontWeight: 700, color: '#f43f5e' }}>{unhealthyCount}</Typography>
                    <Typography variant="caption" sx={{ color: '#64748b' }}>异常</Typography>
                  </Box>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={factorHealth.length > 0 ? (healthyCount / factorHealth.length) * 100 : 0}
                  sx={{
                    height: 8, borderRadius: 4, mb: 1,
                    backgroundColor: 'rgba(148, 163, 184, 0.1)',
                    '& .MuiLinearProgress-bar': { backgroundColor: '#10b981', borderRadius: 4 },
                  }}
                />
                <Typography variant="caption" sx={{ color: '#64748b' }}>
                  健康率 {factorHealth.length > 0 ? ((healthyCount / factorHealth.length) * 100).toFixed(0) : 0}%
                </Typography>
              </Box>
            ) : (
              <Typography sx={{ color: '#64748b' }}>暂无因子健康数据</Typography>
            )}
          </GlassPanel>
        </Grid>

        {/* Recent alerts */}
        <Grid size={{ xs: 12, md: 6 }}>
          <GlassPanel animate={false} sx={{ height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>最新告警</Typography>
              <Button size="small" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/app/monitor')}>
                查看全部
              </Button>
            </Box>
            {alerts.length > 0 ? (
              <Box>
                {alerts.map((a) => (
                  <Box key={a.alert_id} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.75, borderBottom: '1px solid rgba(148, 163, 184, 0.06)' }}>
                    <NeonChip
                      label={a.severity === 'critical' ? '严重' : a.severity === 'warning' ? '警告' : '信息'}
                      size="small"
                      neonColor={a.severity === 'critical' ? 'red' : a.severity === 'warning' ? 'amber' : 'default'}
                    />
                    <Typography variant="body2" sx={{ flex: 1, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.message || a.object_name || '-'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#64748b', whiteSpace: 'nowrap' }}>
                      {a.alert_time?.slice(5, 16).replace('T', ' ')}
                    </Typography>
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography sx={{ color: '#64748b' }}>暂无告警</Typography>
            )}
          </GlassPanel>
        </Grid>

        {/* Quick links */}
        <Grid size={{ xs: 12, md: 6 }}>
          <GlassPanel animate={false} sx={{ height: '100%' }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>快捷入口</Typography>
            <Grid container spacing={1.5}>
              {quickLinks.map((link) => (
                <Grid size={{ xs: 6, sm: 3 }} key={link.path}>
                  <Box
                    onClick={() => navigate(link.path)}
                    sx={{
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5,
                      p: 2, borderRadius: 2, cursor: 'pointer',
                      border: '1px solid rgba(148, 163, 184, 0.08)',
                      transition: 'all 0.2s ease',
                      '&:hover': { backgroundColor: 'rgba(148, 163, 184, 0.06)', borderColor: `${link.color}33` },
                    }}
                  >
                    <Box sx={{ color: link.color }}>{link.icon}</Box>
                    <Typography variant="caption" sx={{ color: '#94a3b8' }}>{link.label}</Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </GlassPanel>
        </Grid>
      </Grid>
    </Box>
  );
}
