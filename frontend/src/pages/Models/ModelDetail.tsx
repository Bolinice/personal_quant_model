import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Grid, Table, TableBody, TableCell,
  TableHead, TableRow, Tabs, Tab, Button, Snackbar, Alert, Chip,
  Select, MenuItem, FormControl, InputLabel, List, ListItem, ListItemIcon, ListItemText,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AssessmentIcon from '@mui/icons-material/Assessment';
import LockIcon from '@mui/icons-material/Lock';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import HistoryIcon from '@mui/icons-material/History';
import ApiIcon from '@mui/icons-material/Api';
import GroupIcon from '@mui/icons-material/Group';
import DescriptionIcon from '@mui/icons-material/Description';
import { stockPoolApi, modelApi, subscriptionApi } from '@/api';
import type { StockPool, Model, ModelPerformance, ModelScore } from '@/api';
import { PageHeader, GlassPanel, GlassTable, NeonChip, MetricCard } from '@/components/ui';
import PaywallPanel from '@/components/ui/PaywallPanel';
import { useLang } from '@/i18n';

const FREE_POOLS = new Set(['HS300', 'ZZ500']);
const POOL_NEON: Record<string, 'cyan' | 'purple' | 'green' | 'amber'> = {
  HS300: 'cyan', ZZ500: 'purple', ZZ1000: 'green', ALL_A: 'amber',
};
const POOL_NAMES: Record<string, string> = {
  HS300: '沪深300', ZZ500: '中证500', ZZ1000: '中证1000', ALL_A: '全A股',
};

const fmt = (v: number | null | undefined, pct = false) => {
  if (v == null) return '-';
  return pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(4);
};

function getUserId(): number {
  return Number(localStorage.getItem('user_id') || '1');
}

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return value === index ? <Box sx={{ py: 3 }}>{children}</Box> : null;
}

export default function ModelDetail() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { t } = useLang();
  const [tab, setTab] = useState(0);
  const [pool, setPool] = useState<StockPool | null>(null);
  const [model, setModel] = useState<Model | null>(null);
  const [performance, setPerformance] = useState<ModelPerformance[]>([]);
  const [scores, setScores] = useState<ModelScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [locked, setLocked] = useState(false);
  const [exportFormat, setExportFormat] = useState('csv');

  const isPaidPool = code ? !FREE_POOLS.has(code) : false;

  useEffect(() => {
    if (!code) return;
    (async () => {
      try {
        const poolRes = await stockPoolApi.get(code);
        setPool(poolRes.data);

        if (isPaidPool) {
          try {
            const accessRes = await subscriptionApi.checkAccess(getUserId(), code);
            if (!accessRes.data.has_access) {
              setLocked(true);
              setLoading(false);
              return;
            }
          } catch {
            setLocked(true);
            setLoading(false);
            return;
          }
        }

        const modelsRes = await modelApi.list({ limit: 200 });
        const matched = modelsRes.data.find((m) =>
          m.model_code.toUpperCase().includes(code.toUpperCase())
        );
        if (matched) {
          setModel(matched);
          let perfData: ModelPerformance[] = [];
          try {
            const perfRes = await modelApi.getPerformance(matched.id, { limit: 200 });
            perfData = perfRes.data;
            setPerformance(perfData);
          } catch { /* no performance data */ }

          if (perfData.length > 0) {
            const latestDate = perfData[0].trade_date;
            try {
              const scoresRes = await modelApi.getScores(matched.id, latestDate);
              setScores(scoresRes.data);
            } catch { /* no scores */ }
          }
        }
      } catch {
        setError('加载策略报告失败');
      } finally {
        setLoading(false);
      }
    })();
  }, [code]);

  if (loading) return <Typography>加载中...</Typography>;

  if (!pool) {
    return (
      <Box>
        <Typography>未知的股票池: {code}</Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/app/models')} sx={{ mt: 2 }}>返回</Button>
      </Box>
    );
  }

  const neon = POOL_NEON[pool.pool_code];
  const latest = performance.length > 0 ? performance[0] : null;

  // Compute metrics
  const metrics = {
    annualReturn: latest?.cumulative_return ?? null,
    maxDrawdown: latest?.max_drawdown ?? null,
    sharpe: latest?.sharpe_ratio ?? null,
    volatility: performance.length > 1
      ? Math.sqrt(performance.filter(p => p.daily_return != null).reduce((s, p) => s + Math.pow((p.daily_return ?? 0), 2), 0) / performance.length) * Math.sqrt(252)
      : null,
    winRate: performance.length > 0
      ? performance.filter(p => (p.daily_return ?? 0) >= 0).length / performance.length
      : null,
    turnover: performance.length > 0
      ? performance.reduce((s, p) => s + (p.turnover ?? 0), 0) / performance.length
      : null,
  };

  const tabLabels = [
    t.models.tabBasic,
    t.models.tabBacktest,
    t.models.tabPositions,
    t.models.tabExport,
    t.models.tabApi,
    t.models.tabPermissions,
    t.models.tabLogs,
  ];

  return (
    <Box>
      <PageHeader
        title={`${pool.pool_name} ${t.models.myModels}`}
        actions={<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/app/models')}>{t.btn.back}</Button>}
      />
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <NeonChip label={pool.pool_name} size="small" neonColor={neon || 'default'} />
        {pool.base_index_code && <NeonChip label={pool.base_index_code} size="small" neonColor="indigo" />}
        {model && <NeonChip label={`v${model.version}`} size="small" neonColor="indigo" />}
      </Box>

      {locked ? (
        <PaywallPanel poolName={POOL_NAMES[code!] || pool.pool_name} />
      ) : (
        <>
          {/* Tabs */}
          <Box sx={{ borderBottom: '1px solid rgba(148, 163, 184, 0.1)', mb: 1 }}>
            <Tabs
              value={tab}
              onChange={(_, v) => setTab(v)}
              variant="scrollable"
              scrollButtons="auto"
            >
              {tabLabels.map((label, i) => (
                <Tab key={i} label={label} sx={{ minHeight: 44 }} />
              ))}
            </Tabs>
          </Box>

          {/* Tab 1: Basic Info */}
          <TabPanel value={tab} index={0}>
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12, md: 6 }}>
                <GlassPanel animate={false}>
                  <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>基础信息</Typography>
                  {[
                    ['模型名称', model?.model_name || pool.pool_name],
                    ['模型代码', model?.model_code || code],
                    ['描述', model?.description || `${pool.pool_name}增强策略`],
                    ['股票池', pool.pool_name],
                    ['基准指数', pool.base_index_code || '-'],
                    ['版本', model?.version || '-'],
                    ['状态', model?.status === 'active' ? '运行中' : '已停用'],
                    ['创建时间', model?.created_at?.slice(0, 10) || '-'],
                    ['更新时间', model?.updated_at?.slice(0, 10) || '-'],
                  ].map(([label, value]) => (
                    <Box key={label as string} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.75, borderBottom: '1px solid rgba(148, 163, 184, 0.06)' }}>
                      <Typography variant="body2" sx={{ color: '#64748b' }}>{label}</Typography>
                      <Typography variant="body2" sx={{ color: '#e2e8f0', fontWeight: 500 }}>{value}</Typography>
                    </Box>
                  ))}
                </GlassPanel>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <GlassPanel animate={false}>
                  <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>因子权重</Typography>
                  {model?.factor_weights && Object.keys(model.factor_weights).length > 0 ? (
                    <List dense>
                      {Object.entries(model.factor_weights).map(([factor, weight]) => (
                        <ListItem key={factor} sx={{ px: 0 }}>
                          <ListItemText primary={factor} sx={{ '& .MuiListItemText-primary': { color: '#94a3b8', fontSize: '0.85rem' } }} />
                          <Typography sx={{ color: '#22d3ee', fontWeight: 600, fontSize: '0.85rem' }}>
                            {(weight as number).toFixed(4)}
                          </Typography>
                        </ListItem>
                      ))}
                    </List>
                  ) : (
                    <Typography sx={{ color: '#64748b' }}>暂无因子权重数据</Typography>
                  )}
                </GlassPanel>
              </Grid>
            </Grid>
          </TabPanel>

          {/* Tab 2: Backtest Results */}
          <TabPanel value={tab} index={1}>
            {/* Key metrics */}
            <Grid container spacing={2.5} sx={{ mb: 3 }}>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <MetricCard label={t.models.annualReturn} value={fmt(metrics.annualReturn, true)} color="#22d3ee" icon={<TrendingUpIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <MetricCard label={t.models.maxDrawdown} value={fmt(metrics.maxDrawdown, true)} color="#f43f5e" icon={<AssessmentIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <MetricCard label={t.models.sharpe} value={fmt(metrics.sharpe)} color="#8b5cf6" icon={<ShowChartIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <MetricCard label={t.models.volatility} value={fmt(metrics.volatility, true)} color="#f59e0b" icon={<AssessmentIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <MetricCard label={t.models.winRate} value={fmt(metrics.winRate, true)} color="#10b981" icon={<TrendingUpIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <MetricCard label={t.models.turnover} value={fmt(metrics.turnover, true)} color="#6366f1" icon={<AssessmentIcon />} />
              </Grid>
            </Grid>

            {/* Chart placeholder */}
            <Grid container spacing={2.5} sx={{ mb: 3 }}>
              <Grid size={{ xs: 12, md: 6 }}>
                <GlassPanel animate={false}>
                  <Typography sx={{ fontWeight: 600, mb: 1.5 }}>收益曲线</Typography>
                  <Box sx={{
                    height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'linear-gradient(180deg, rgba(34, 211, 238, 0.03) 0%, rgba(139, 92, 246, 0.03) 100%)',
                    borderRadius: 2, border: '1px dashed rgba(148, 163, 184, 0.15)',
                  }}>
                    <Typography sx={{ color: '#64748b' }}>图表区域</Typography>
                  </Box>
                </GlassPanel>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <GlassPanel animate={false}>
                  <Typography sx={{ fontWeight: 600, mb: 1.5 }}>回撤曲线</Typography>
                  <Box sx={{
                    height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'linear-gradient(180deg, rgba(244, 63, 94, 0.03) 0%, rgba(245, 158, 11, 0.03) 100%)',
                    borderRadius: 2, border: '1px dashed rgba(148, 163, 184, 0.15)',
                  }}>
                    <Typography sx={{ color: '#64748b' }}>图表区域</Typography>
                  </Box>
                </GlassPanel>
              </Grid>
            </Grid>

            {/* Performance history */}
            <GlassPanel animate={false}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>策略表现</Typography>
              <GlassTable>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>日期</TableCell>
                      <TableCell>日收益</TableCell>
                      <TableCell>累计收益</TableCell>
                      <TableCell>最大回撤</TableCell>
                      <TableCell>夏普比率</TableCell>
                      <TableCell>IC</TableCell>
                      <TableCell>Rank IC</TableCell>
                      <TableCell>换手率</TableCell>
                      <TableCell>持仓数</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {performance.map((p) => (
                      <TableRow key={p.id} hover>
                        <TableCell>{p.trade_date?.slice(0, 10)}</TableCell>
                        <TableCell sx={{ color: (p.daily_return ?? 0) >= 0 ? '#22d3ee' : '#f43f5e' }}>{fmt(p.daily_return, true)}</TableCell>
                        <TableCell sx={{ color: (p.cumulative_return ?? 0) >= 0 ? '#22d3ee' : '#f43f5e' }}>{fmt(p.cumulative_return, true)}</TableCell>
                        <TableCell sx={{ color: '#f43f5e' }}>{fmt(p.max_drawdown, true)}</TableCell>
                        <TableCell>{fmt(p.sharpe_ratio)}</TableCell>
                        <TableCell>{fmt(p.ic)}</TableCell>
                        <TableCell>{fmt(p.rank_ic)}</TableCell>
                        <TableCell>{fmt(p.turnover, true)}</TableCell>
                        <TableCell>{p.num_selected ?? '-'}</TableCell>
                      </TableRow>
                    ))}
                    {performance.length === 0 && <TableRow><TableCell colSpan={9} align="center">暂无策略表现数据</TableCell></TableRow>}
                  </TableBody>
                </Table>
              </GlassTable>
            </GlassPanel>
          </TabPanel>

          {/* Tab 3: Positions & Rebalances */}
          <TabPanel value={tab} index={2}>
            <GlassPanel animate={false} sx={{ mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>最新持仓评分</Typography>
              {scores.length > 0 ? (
                <GlassTable>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>证券代码</TableCell>
                        <TableCell>综合得分</TableCell>
                        <TableCell>排名</TableCell>
                        <TableCell>分位</TableCell>
                        <TableCell>入选</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {scores.slice(0, 100).map((s) => (
                        <TableRow key={s.id} hover>
                          <TableCell sx={{ fontFamily: 'monospace' }}>{s.security_id}</TableCell>
                          <TableCell>{s.score?.toFixed(4) ?? '-'}</TableCell>
                          <TableCell>{s.rank ?? '-'}</TableCell>
                          <TableCell>{s.quantile != null ? `${(s.quantile * 100).toFixed(1)}%` : '-'}</TableCell>
                          <TableCell><NeonChip label={s.is_selected ? '入选' : '未入选'} size="small" neonColor={s.is_selected ? 'green' : 'default'} /></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </GlassTable>
              ) : (
                <Typography sx={{ color: '#64748b', py: 2 }}>暂无持仓数据</Typography>
              )}
            </GlassPanel>

            <GlassPanel animate={false}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>历史调仓记录</Typography>
              <Typography sx={{ color: '#64748b', py: 2 }}>调仓记录将在模型运行后生成</Typography>
            </GlassPanel>
          </TabPanel>

          {/* Tab 4: Data & Export */}
          <TabPanel value={tab} index={3}>
            <Grid container spacing={2.5}>
              <Grid size={{ xs: 12, md: 6 }}>
                <GlassPanel animate={false}>
                  <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>{t.models.dataExport}</Typography>
                  <List>
                    {[
                      { name: '持仓评分', desc: '最新持仓股票及评分', available: true },
                      { name: '策略表现', desc: '历史策略表现数据', available: true },
                      { name: '因子权重', desc: '模型因子权重配置', available: true },
                      { name: '交易记录', desc: '历史调仓交易明细', available: false },
                      { name: '风险分析', desc: '风险指标与暴露度', available: false },
                    ].map((item) => (
                      <ListItem key={item.name} sx={{ px: 0 }}>
                        <ListItemIcon sx={{ minWidth: 32 }}>
                          <CheckCircleIcon sx={{ fontSize: 18, color: item.available ? '#10b981' : '#64748b' }} />
                        </ListItemIcon>
                        <ListItemText
                          primary={item.name}
                          secondary={item.desc}
                          sx={{ '& .MuiListItemText-primary': { color: item.available ? '#e2e8f0' : '#64748b', fontSize: '0.9rem' }, '& .MuiListItemText-secondary': { color: '#64748b', fontSize: '0.75rem' } }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </GlassPanel>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <GlassPanel animate={false}>
                  <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>导出设置</Typography>
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel sx={{ color: '#94a3b8' }}>导出格式</InputLabel>
                    <Select value={exportFormat} label="导出格式" onChange={(e) => setExportFormat(e.target.value)} sx={{ color: '#e2e8f0' }}>
                      <MenuItem value="csv">{t.models.exportCSV}</MenuItem>
                      <MenuItem value="excel">{t.models.exportExcel}</MenuItem>
                      <MenuItem value="json">{t.models.exportJSON}</MenuItem>
                    </Select>
                  </FormControl>
                  <Button
                    variant="contained"
                    startIcon={<FileDownloadIcon />}
                    fullWidth
                    sx={{ mb: 3 }}
                  >
                    {t.models.exportNow}
                  </Button>

                  <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>{t.models.exportHistory}</Typography>
                  <Typography sx={{ color: '#64748b' }}>暂无导出记录</Typography>
                </GlassPanel>
              </Grid>
            </Grid>
          </TabPanel>

          {/* Tab 5: API Mapping (locked) */}
          <TabPanel value={tab} index={4}>
            <Box sx={{ position: 'relative', minHeight: 300 }}>
              <Box sx={{
                position: 'absolute', inset: 0, zIndex: 1,
                backdropFilter: 'blur(8px)', backgroundColor: 'rgba(10, 14, 26, 0.6)',
                borderRadius: 3, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 2,
              }}>
                <LockIcon sx={{ fontSize: 48, color: '#f59e0b' }} />
                <Typography sx={{ fontWeight: 600, color: '#f59e0b' }}>{t.models.locked}</Typography>
                <Typography sx={{ color: '#94a3b8', textAlign: 'center', maxWidth: 400 }}>{t.models.apiLocked}</Typography>
                <Button variant="contained" onClick={() => navigate('/app/models/plan')}>{t.models.unlockUpgrade}</Button>
              </Box>
              <GlassPanel animate={false}>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>API 端点映射</Typography>
                <Typography sx={{ color: '#64748b' }}>API 接入功能允许您通过 REST API 获取模型数据、持仓评分和策略表现。</Typography>
              </GlassPanel>
            </Box>
          </TabPanel>

          {/* Tab 6: Permissions & Sharing (locked) */}
          <TabPanel value={tab} index={5}>
            <Box sx={{ position: 'relative', minHeight: 300 }}>
              <Box sx={{
                position: 'absolute', inset: 0, zIndex: 1,
                backdropFilter: 'blur(8px)', backgroundColor: 'rgba(10, 14, 26, 0.6)',
                borderRadius: 3, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 2,
              }}>
                <LockIcon sx={{ fontSize: 48, color: '#f59e0b' }} />
                <Typography sx={{ fontWeight: 600, color: '#f59e0b' }}>{t.models.locked}</Typography>
                <Typography sx={{ color: '#94a3b8', textAlign: 'center', maxWidth: 400 }}>{t.models.teamLocked}</Typography>
                <Button variant="contained" onClick={() => navigate('/app/models/plan')}>{t.models.unlockUpgrade}</Button>
              </Box>
              <GlassPanel animate={false}>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>权限与共享</Typography>
                <Typography sx={{ color: '#64748b' }}>团队共享功能允许您与团队成员共享模型、协作编辑和统一管理。</Typography>
              </GlassPanel>
            </Box>
          </TabPanel>

          {/* Tab 7: Run Logs */}
          <TabPanel value={tab} index={6}>
            <GlassPanel animate={false}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>{t.models.tabLogs}</Typography>
              <List>
                {model ? [
                  { time: model.updated_at, action: '模型更新', status: 'success' },
                  { time: model.created_at, action: '模型创建', status: 'success' },
                ].map((log, i) => (
                  <ListItem key={i} sx={{ px: 0, borderBottom: '1px solid rgba(148, 163, 184, 0.06)' }}>
                    <ListItemIcon sx={{ minWidth: 32 }}>
                      <HistoryIcon sx={{ fontSize: 18, color: '#64748b' }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={log.action}
                      secondary={log.time?.slice(0, 19).replace('T', ' ')}
                      sx={{ '& .MuiListItemText-primary': { color: '#e2e8f0', fontSize: '0.85rem' }, '& .MuiListItemText-secondary': { color: '#64748b', fontSize: '0.75rem' } }}
                    />
                    <NeonChip label="成功" size="small" neonColor="green" />
                  </ListItem>
                )) : (
                  <Typography sx={{ color: '#64748b', py: 2 }}>暂无运行日志</Typography>
                )}
              </List>
            </GlassPanel>
          </TabPanel>
        </>
      )}

      <Snackbar open={!!error} autoHideDuration={3000} onClose={() => setError('')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
    </Box>
  );
}
