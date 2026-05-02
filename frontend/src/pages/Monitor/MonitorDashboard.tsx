import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Button,
  Tabs,
  Tab,
  Snackbar,
  Alert,
  CircularProgress,
} from '@mui/material';
import { motion } from 'framer-motion';
import { monitorApi } from '@/api';
import type { MonitorFactorHealth, MonitorModelHealth, MonitorAlert, Regime } from '@/api';
import { PageHeader, GlassPanel, NeonChip, MetricCard } from '@/components/ui';

// regimeLabel：后端regime枚举到中文的映射，trending/range_bound/defensive/aggressive
// 对应趋势/震荡/防御/进攻四种市场状态，regime模块根据波动率和趋势强度判定
const regimeLabel: Record<string, string> = {
  trending: '趋势',
  range_bound: '震荡',
  defensive: '防御',
  aggressive: '进攻',
};
// regimeColor：防御(红)表示应降低仓位，进攻(绿)表示可加仓，震荡(橙)表示需谨慎
const regimeColor: Record<string, string> = {
  trending: '#22d3ee',
  range_bound: '#f59e0b',
  defensive: '#f43f5e',
  aggressive: '#10b981',
};
const healthNeon: Record<string, 'green' | 'amber' | 'red' | 'default'> = {
  healthy: 'green',
  warning: 'amber',
  unhealthy: 'red',
};
const severityNeon: Record<string, 'red' | 'amber' | 'default'> = {
  critical: 'red',
  warning: 'amber',
  info: 'default',
};

export default function MonitorDashboard() {
  const [tab, setTab] = useState(0);
  const [regime, setRegime] = useState<Regime | null>(null);
  const [factorHealth, setFactorHealth] = useState<MonitorFactorHealth[]>([]);
  const [modelHealth, setModelHealth] = useState<MonitorModelHealth[]>([]);
  const [alerts, setAlerts] = useState<MonitorAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    Promise.all([
      monitorApi
        .getRegime()
        .then((res) => setRegime(res.data))
        .catch(() => {}),
      monitorApi
        .getFactorHealth()
        .then((res) => setFactorHealth(res.data))
        .catch(() => {}),
      monitorApi
        .getModelHealth()
        .then((res) => setModelHealth(res.data))
        .catch(() => {}),
      monitorApi
        .getAlerts({ page_size: 50 })
        .then((res) => setAlerts(res.data))
        .catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const handleResolve = async (alertId: number) => {
    try {
      await monitorApi.resolveAlert(alertId);
      setAlerts((prev) =>
        prev.map((a) => (a.alert_id === alertId ? { ...a, resolved_flag: true } : a))
      );
      setSnackbar({ open: true, message: '告警已解决', severity: 'success' });
    } catch {
      setSnackbar({ open: true, message: '解决失败', severity: 'error' });
    }
  };

  const unresolvedAlerts = alerts.filter((a) => !a.resolved_flag);

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
        title="监控中心"
        subtitle="实时监控因子健康、模型状态和系统告警"
        breadcrumbs={[
          { label: '首页', path: '/' },
          { label: '监控中心' },
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
          <GlassPanel>
            <Typography
              sx={{
                fontSize: '0.75rem',
                color: '#64748b',
                mb: 1.5,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              市场状态
            </Typography>
            {regime ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Box
                  sx={{
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    bgcolor: regimeColor[regime.regime] || '#94a3b8',
                    boxShadow: `0 0 12px ${regimeColor[regime.regime] || '#94a3b8'}40`,
                  }}
                />
                <Box>
                  <Typography
                    sx={{
                      fontWeight: 700,
                      color: regimeColor[regime.regime] || '#e2e8f0',
                      fontSize: '1.25rem',
                      lineHeight: 1.2,
                    }}
                  >
                    {regimeLabel[regime.regime] || regime.regime}
                  </Typography>
                  {regime.confidence != null && (
                    <Typography
                      sx={{
                        fontSize: '0.75rem',
                        color: '#64748b',
                        mt: 0.25,
                      }}
                    >
                      置信度 {(regime.confidence * 100).toFixed(0)}%
                    </Typography>
                  )}
                </Box>
              </Box>
            ) : (
              <Typography sx={{ color: '#64748b', fontSize: '0.9375rem' }}>暂无数据</Typography>
            )}
          </GlassPanel>

          <MetricCard label="因子健康" value={factorHealth.length} color="#22d3ee" />
          <MetricCard label="模型健康" value={modelHealth.length} color="#8b5cf6" />
          <MetricCard
            label="未解决告警"
            value={unresolvedAlerts.length}
            color={unresolvedAlerts.length > 0 ? '#f43f5e' : '#10b981'}
          />
        </Box>
      </motion.div>

      {/* 标签页 */}
      <Box
        sx={{
          borderBottom: '1px solid rgba(148, 163, 184, 0.08)',
          mb: 3,
        }}
      >
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{
            '& .MuiTab-root': {
              color: '#64748b',
              fontWeight: 600,
              textTransform: 'none',
              fontSize: '0.9375rem',
              '&.Mui-selected': {
                color: '#22d3ee',
              },
            },
            '& .MuiTabs-indicator': {
              background: 'linear-gradient(90deg, #22d3ee 0%, #3b82f6 100%)',
              height: 3,
              borderRadius: '3px 3px 0 0',
            },
          }}
        >
          <Tab label="因子健康" />
          <Tab label="模型健康" />
          <Tab label="告警列表" />
        </Tabs>
      </Box>

      {/* 因子健康 */}
      {tab === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <GlassPanel>
            <Box sx={{ overflowX: 'auto' }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>日期</TableCell>
                    <TableCell>因子名称</TableCell>
                    <TableCell>覆盖率</TableCell>
                    <TableCell>IC均值</TableCell>
                    <TableCell>ICIR</TableCell>
                    <TableCell>PSI</TableCell>
                    <TableCell>状态</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {factorHealth.map((h, i) => (
                    <TableRow key={i}>
                      <TableCell>{h.trade_date}</TableCell>
                      <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.8125rem' }}>
                        {h.factor_name}
                      </TableCell>
                      <TableCell>
                        {h.coverage_rate != null ? `${(h.coverage_rate * 100).toFixed(1)}%` : '-'}
                      </TableCell>
                      <TableCell>
                        <Typography
                          sx={{
                            color: h.ic_mean != null && h.ic_mean > 0 ? '#10b981' : '#ef4444',
                            fontWeight: 600,
                            fontSize: '0.875rem',
                          }}
                        >
                          {h.ic_mean != null ? h.ic_mean.toFixed(4) : '-'}
                        </Typography>
                      </TableCell>
                      <TableCell>{h.icir != null ? h.icir.toFixed(2) : '-'}</TableCell>
                      <TableCell>{h.psi != null ? h.psi.toFixed(4) : '-'}</TableCell>
                      <TableCell>
                        <NeonChip
                          label={
                            h.health_status === 'healthy'
                              ? '健康'
                              : h.health_status === 'warning'
                                ? '警告'
                                : '异常'
                          }
                          size="small"
                          neonColor={healthNeon[h.health_status] || 'default'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {factorHealth.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} align="center" sx={{ py: 4, color: '#64748b' }}>
                        暂无因子健康数据
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
          </GlassPanel>
        </motion.div>
      )}

      {/* 模型健康 */}
      {tab === 1 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <GlassPanel>
            <Box sx={{ overflowX: 'auto' }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>日期</TableCell>
                    <TableCell>模型ID</TableCell>
                    <TableCell>预测漂移</TableCell>
                    <TableCell>特征重要性漂移</TableCell>
                    <TableCell>OOS得分</TableCell>
                    <TableCell>状态</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {modelHealth.map((h, i) => (
                    <TableRow key={i}>
                      <TableCell>{h.trade_date}</TableCell>
                      <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.8125rem' }}>
                        {h.model_id}
                      </TableCell>
                      <TableCell>
                        {h.prediction_drift != null ? h.prediction_drift.toFixed(4) : '-'}
                      </TableCell>
                      <TableCell>
                        {h.feature_importance_drift != null
                          ? h.feature_importance_drift.toFixed(4)
                          : '-'}
                      </TableCell>
                      <TableCell>{h.oos_score != null ? h.oos_score.toFixed(4) : '-'}</TableCell>
                      <TableCell>
                        <NeonChip
                          label={
                            h.health_status === 'healthy'
                              ? '健康'
                              : h.health_status === 'warning'
                                ? '警告'
                                : '异常'
                          }
                          size="small"
                          neonColor={healthNeon[h.health_status] || 'default'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {modelHealth.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} align="center" sx={{ py: 4, color: '#64748b' }}>
                        暂无模型健康数据
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
          </GlassPanel>
        </motion.div>
      )}

      {/* 告警列表 */}
      {tab === 2 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <GlassPanel>
            <Box sx={{ overflowX: 'auto' }}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>时间</TableCell>
                    <TableCell>类型</TableCell>
                    <TableCell>严重程度</TableCell>
                    <TableCell>对象</TableCell>
                    <TableCell>消息</TableCell>
                    <TableCell>状态</TableCell>
                    <TableCell>操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {alerts.map((a) => (
                    <TableRow key={a.alert_id}>
                      <TableCell sx={{ fontSize: '0.8125rem' }}>
                        {a.alert_time?.slice(0, 19).replace('T', ' ')}
                      </TableCell>
                      <TableCell>{a.alert_type || '-'}</TableCell>
                      <TableCell>
                        <NeonChip
                          label={
                            a.severity === 'critical'
                              ? '严重'
                              : a.severity === 'warning'
                                ? '警告'
                                : '信息'
                          }
                          size="small"
                          neonColor={severityNeon[a.severity || ''] || 'default'}
                        />
                      </TableCell>
                      <TableCell>{a.object_name || '-'}</TableCell>
                      <TableCell
                        sx={{
                          maxWidth: 300,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {a.message || '-'}
                      </TableCell>
                      <TableCell>
                        <NeonChip
                          label={a.resolved_flag ? '已解决' : '未解决'}
                          size="small"
                          neonColor={a.resolved_flag ? 'green' : 'red'}
                        />
                      </TableCell>
                      <TableCell>
                        {!a.resolved_flag && (
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleResolve(a.alert_id)}
                            sx={{
                              borderColor: 'rgba(34, 211, 238, 0.3)',
                              color: '#22d3ee',
                              textTransform: 'none',
                              fontSize: '0.8125rem',
                              '&:hover': {
                                borderColor: 'rgba(34, 211, 238, 0.5)',
                                backgroundColor: 'rgba(34, 211, 238, 0.1)',
                              },
                            }}
                          >
                            解决
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {alerts.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} align="center" sx={{ py: 4, color: '#64748b' }}>
                        暂无告警
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
          </GlassPanel>
        </motion.div>
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
