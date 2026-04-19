import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Grid, Table, TableBody, TableCell,
  TableHead, TableRow, Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import Button from '@mui/material/Button';
import { stockPoolApi, modelApi, subscriptionApi } from '@/api';
import type { StockPool, Model, ModelPerformance, ModelScore } from '@/api';
import { PageHeader, GlassPanel, GlassTable, NeonChip, MetricCard } from '@/components/ui';
import PaywallPanel from '@/components/ui/PaywallPanel';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AssessmentIcon from '@mui/icons-material/Assessment';

const FREE_POOLS = new Set(['HS300', 'ZZ500']);

const POOL_NEON: Record<string, 'cyan' | 'purple' | 'green' | 'amber'> = {
  HS300: 'cyan', ZZ500: 'purple', ZZ1000: 'green', ALL_A: 'amber',
};

const POOL_NAMES: Record<string, string> = {
  HS300: '沪深300', ZZ500: '中证500', ZZ1000: '中证1000', ALL_A: '全A股',
};

const fmt = (v: number | null | undefined, pct = false) => {
  if (v == null) return '-';
  const s = pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(4);
  return s;
};

function getUserId(): number {
  return Number(localStorage.getItem('user_id') || '1');
}

export default function ModelDetail() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [pool, setPool] = useState<StockPool | null>(null);
  const [model, setModel] = useState<Model | null>(null);
  const [performance, setPerformance] = useState<ModelPerformance[]>([]);
  const [scores, setScores] = useState<ModelScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [locked, setLocked] = useState(false);

  const isPaidPool = code ? !FREE_POOLS.has(code) : false;

  useEffect(() => {
    if (!code) return;

    (async () => {
      try {
        const poolRes = await stockPoolApi.get(code);
        setPool(poolRes.data);

        // If paid pool, check access via backend
        if (isPaidPool) {
          try {
            const accessRes = await subscriptionApi.checkAccess(getUserId(), code);
            if (!accessRes.data.has_access) {
              setLocked(true);
              setLoading(false);
              return;
            }
          } catch {
            // API failed (e.g. not logged in) — treat as locked
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
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/models')} sx={{ mt: 2 }}>返回</Button>
      </Box>
    );
  }

  const neon = POOL_NEON[pool.pool_code];
  const latest = performance.length > 0 ? performance[0] : null;

  return (
    <Box>
      <PageHeader
        title={`${pool.pool_name} 策略报告`}
        actions={<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/models')}>返回</Button>}
      />
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <NeonChip label={pool.pool_name} size="small" neonColor={neon || 'default'} />
        {pool.base_index_code && <NeonChip label={pool.base_index_code} size="small" neonColor="indigo" />}
        {model && <NeonChip label={`v${model.version}`} size="small" neonColor="indigo" />}
      </Box>

      {/* Paywall for paid pools */}
      {locked ? (
        <PaywallPanel poolName={POOL_NAMES[code!] || pool.pool_name} />
      ) : (
        <>
          {/* Key metrics from latest performance */}
          {latest && (
            <Grid container spacing={2.5} sx={{ mb: 3 }}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <MetricCard label="累计收益" value={fmt(latest.cumulative_return, true)} color="#22d3ee" icon={<TrendingUpIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <MetricCard label="夏普比率" value={fmt(latest.sharpe_ratio)} color="#8b5cf6" icon={<ShowChartIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <MetricCard label="最大回撤" value={fmt(latest.max_drawdown, true)} color="#f43f5e" icon={<AssessmentIcon />} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <MetricCard label="换手率" value={fmt(latest.turnover, true)} color="#f59e0b" icon={<AssessmentIcon />} />
              </Grid>
            </Grid>
          )}

          {/* Performance history table */}
          <GlassPanel sx={{ mb: 3 }}>
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

          {/* Latest scores table */}
          {scores.length > 0 && (
            <GlassPanel>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>最新持仓评分</Typography>
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
            </GlassPanel>
          )}
        </>
      )}

      <Snackbar open={!!error} autoHideDuration={3000} onClose={() => setError('')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
    </Box>
  );
}