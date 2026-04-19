import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Grid, Button, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AssessmentIcon from '@mui/icons-material/Assessment';
import { backtestApi, performanceApi } from '@/api';
import type { Backtest, BacktestResult, BacktestTrade } from '@/api';
import type { PerformanceAnalysis } from '@/api';
import { PageHeader, GlassPanel, MetricCard, NeonChip } from '@/components/ui';

const statusNeonColor: Record<string, 'default' | 'cyan' | 'green' | 'red' | 'amber'> = {
  pending: 'default', running: 'cyan', completed: 'green', failed: 'red', cancelled: 'amber',
};
const statusLabel: Record<string, string> = {
  pending: '待运行', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消',
};

export default function BacktestResultPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [analysis, setAnalysis] = useState<PerformanceAnalysis | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    if (id) {
      backtestApi.get(Number(id)).then((res) => setBacktest(res.data)).catch(() => {});
      backtestApi.getResult(Number(id)).then((res) => setResult(res.data)).catch(() => {});
      backtestApi.getTrades(Number(id)).then((res) => setTrades(res.data)).catch(() => {});
      performanceApi.getBacktestAnalysis(Number(id)).then((res) => setAnalysis(res.data)).catch(() => {});
    }
  }, [id]);

  const handleRun = async () => {
    try {
      await backtestApi.run(Number(id));
      setSnackbar({ open: true, message: '回测已启动', severity: 'success' });
      setTimeout(() => window.location.reload(), 2000);
    } catch { setSnackbar({ open: true, message: '启动失败', severity: 'error' }); }
  };

  const handleGenerateReport = async () => {
    try {
      await performanceApi.generateReport(Number(id));
      setSnackbar({ open: true, message: '报告生成成功', severity: 'success' });
    } catch { setSnackbar({ open: true, message: '生成失败', severity: 'error' }); }
  };

  if (!backtest) return <Typography>加载中...</Typography>;

  return (
    <Box>
      <PageHeader
        title={backtest.name}
        actions={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/backtests')}>返回</Button>
            {backtest.status === 'pending' && (
              <Button variant="contained" size="small" startIcon={<PlayArrowIcon />} onClick={handleRun}>运行</Button>
            )}
          </Box>
        }
      />
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <NeonChip label={statusLabel[backtest.status] || backtest.status} size="small" neonColor={statusNeonColor[backtest.status]} />
      </Box>

      <GlassPanel sx={{ mb: 3 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">开始日期</Typography><Typography>{backtest.start_date?.slice(0, 10)}</Typography></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">结束日期</Typography><Typography>{backtest.end_date?.slice(0, 10)}</Typography></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">初始资金</Typography><Typography>{backtest.initial_capital?.toLocaleString()}</Typography></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">描述</Typography><Typography>{backtest.description || '-'}</Typography></Grid>
        </Grid>
      </GlassPanel>

      {analysis && (
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">绩效指标</Typography>
            <Button variant="outlined" size="small" startIcon={<AssessmentIcon />} onClick={handleGenerateReport}>生成报告</Button>
          </Box>
          <Grid container spacing={2.5}>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="年化收益" value={`${(analysis.annual_return * 100).toFixed(2)}%`} color={analysis.annual_return >= 0 ? '#10b981' : '#f43f5e'} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="超额收益" value={`${(analysis.excess_return * 100).toFixed(2)}%`} color={analysis.excess_return >= 0 ? '#10b981' : '#f43f5e'} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="最大回撤" value={`${(analysis.max_drawdown * 100).toFixed(2)}%`} color="#f43f5e" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="夏普比率" value={analysis.sharpe_ratio.toFixed(2)} color="#8b5cf6" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="卡玛比率" value={analysis.calmar_ratio.toFixed(2)} color="#3b82f6" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="信息比率" value={(analysis.information_ratio ?? 0).toFixed(2)} color="#6366f1" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="索提诺比率" value={(analysis.sortino_ratio ?? 0).toFixed(2)} color="#22d3ee" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="胜率" value={analysis.win_rate != null ? `${(analysis.win_rate * 100).toFixed(1)}%` : '-'} color="#10b981" /></Grid>
          </Grid>
        </Box>
      )}

      {result && (
        <GlassPanel sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>回测结果</Typography>
          <Grid container spacing={2.5}>
            <Grid size={{ xs: 6, sm: 3 }}><MetricCard label="总收益" value={`${(result.total_return * 100).toFixed(2)}%`} color={result.total_return >= 0 ? '#10b981' : '#f43f5e'} /></Grid>
            <Grid size={{ xs: 6, sm: 3 }}><MetricCard label="基准收益" value={`${(result.benchmark_return * 100).toFixed(2)}%`} color="#22d3ee" /></Grid>
            <Grid size={{ xs: 6, sm: 3 }}><MetricCard label="超额收益" value={`${(result.excess_return * 100).toFixed(2)}%`} color={result.excess_return >= 0 ? '#10b981' : '#f43f5e'} /></Grid>
            <Grid size={{ xs: 6, sm: 3 }}><MetricCard label="夏普比率" value={result.sharpe_ratio.toFixed(2)} color="#8b5cf6" /></Grid>
          </Grid>
        </GlassPanel>
      )}

      <GlassPanel>
        <Typography variant="h6" gutterBottom>交易记录</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>日期</TableCell>
                <TableCell>证券ID</TableCell>
                <TableCell>方向</TableCell>
                <TableCell>数量</TableCell>
                <TableCell>价格</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {trades.slice(0, 100).map((t) => (
                <TableRow key={t.id}>
                  <TableCell>{t.trade_date?.slice(0, 10)}</TableCell>
                  <TableCell>{t.security_id}</TableCell>
                  <TableCell><NeonChip label={t.trade_type === 'buy' ? '买入' : '卖出'} size="small" neonColor={t.trade_type === 'buy' ? 'green' : 'red'} /></TableCell>
                  <TableCell>{t.quantity?.toLocaleString()}</TableCell>
                  <TableCell>{t.price?.toFixed(2)}</TableCell>
                </TableRow>
              ))}
              {trades.length === 0 && <TableRow><TableCell colSpan={5} align="center">暂无交易记录</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      </GlassPanel>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
