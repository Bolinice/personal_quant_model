import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Paper, Grid, Button, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Chip, Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AssessmentIcon from '@mui/icons-material/Assessment';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { backtestApi, Backtest, BacktestResult, BacktestTrade } from '../../api/backtests';
import { performanceApi, PerformanceAnalysis } from '../../api/performance';

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

  const metricCard = (label: string, value: string | number, color?: string) => (
    <Paper sx={{ p: 2, textAlign: 'center' }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="h5" sx={{ fontWeight: 700, color: color || 'text.primary' }}>
        {typeof value === 'number' ? value.toFixed(4) : value}
      </Typography>
    </Paper>
  );

  if (!backtest) return <Typography>加载中...</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/backtests')}>返回</Button>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>{backtest.name}</Typography>
        <Chip label={statusLabel[backtest.status] || backtest.status} size="small" />
        {backtest.status === 'pending' && (
          <Button variant="contained" size="small" startIcon={<PlayArrowIcon />} onClick={handleRun}>运行</Button>
        )}
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">开始日期</Typography><Typography>{backtest.start_date?.slice(0, 10)}</Typography></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">结束日期</Typography><Typography>{backtest.end_date?.slice(0, 10)}</Typography></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">初始资金</Typography><Typography>{backtest.initial_capital?.toLocaleString()}</Typography></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><Typography variant="body2" color="text.secondary">描述</Typography><Typography>{backtest.description || '-'}</Typography></Grid>
        </Grid>
      </Paper>

      {analysis && (
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">绩效指标</Typography>
            <Button variant="outlined" size="small" startIcon={<AssessmentIcon />} onClick={handleGenerateReport}>生成报告</Button>
          </Box>
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('年化收益', analysis.annual_return, analysis.annual_return >= 0 ? '#66bb6a' : '#ef5350')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('超额收益', analysis.excess_return, analysis.excess_return >= 0 ? '#66bb6a' : '#ef5350')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('最大回撤', analysis.max_drawdown, '#ef5350')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('夏普比率', analysis.sharpe_ratio)}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('卡玛比率', analysis.calmar_ratio)}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('信息比率', analysis.information_ratio ?? '-')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('索提诺比率', analysis.sortino_ratio ?? '-')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('胜率', analysis.win_rate != null ? `${(analysis.win_rate * 100).toFixed(1)}%` : '-')}</Grid>
          </Grid>
        </Box>
      )}

      {result && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>回测结果</Typography>
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 3 }}>{metricCard('总收益', result.total_return, result.total_return >= 0 ? '#66bb6a' : '#ef5350')}</Grid>
            <Grid size={{ xs: 6, sm: 3 }}>{metricCard('基准收益', result.benchmark_return)}</Grid>
            <Grid size={{ xs: 6, sm: 3 }}>{metricCard('超额收益', result.excess_return)}</Grid>
            <Grid size={{ xs: 6, sm: 3 }}>{metricCard('夏普比率', result.sharpe_ratio)}</Grid>
          </Grid>
        </Paper>
      )}

      <Paper sx={{ p: 2, mb: 3 }}>
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
                  <TableCell><Chip label={t.trade_type === 'buy' ? '买入' : '卖出'} size="small" color={t.trade_type === 'buy' ? 'success' : 'error'} /></TableCell>
                  <TableCell>{t.quantity?.toLocaleString()}</TableCell>
                  <TableCell>{t.price?.toFixed(2)}</TableCell>
                </TableRow>
              ))}
              {trades.length === 0 && <TableRow><TableCell colSpan={5} align="center">暂无交易记录</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
