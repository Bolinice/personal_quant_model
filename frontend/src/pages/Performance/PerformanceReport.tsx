import { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Grid, TextField, MenuItem, Button, Snackbar, Alert,
} from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend } from 'recharts';
import { performanceApi, PerformanceAnalysis, PerformanceReport } from '../../api/performance';
import { backtestApi, Backtest } from '../../api/backtests';

const COLORS = ['#4fc3f7', '#f48fb1', '#66bb6a', '#ffa726', '#ab47bc', '#26a69a', '#ef5350', '#78909c'];

export default function PerformanceReportPage() {
  const [backtests, setBacktests] = useState<Backtest[]>([]);
  const [selectedBacktest, setSelectedBacktest] = useState('');
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [analysis, setAnalysis] = useState<PerformanceAnalysis | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    backtestApi.list({ status: 'completed', limit: 200 }).then((res) => setBacktests(res.data)).catch(() => {});
  }, []);

  const handleGenerate = async () => {
    if (!selectedBacktest) return;
    try {
      const res = await performanceApi.generateReport(Number(selectedBacktest));
      setReport(res.data);
      setAnalysis(res.data.analysis);
      setSnackbar({ open: true, message: '报告生成成功', severity: 'success' });
    } catch { setSnackbar({ open: true, message: '生成失败', severity: 'error' }); }
  };

  const handleLoadAnalysis = async () => {
    if (!selectedBacktest) return;
    try {
      const res = await performanceApi.getBacktestAnalysis(Number(selectedBacktest));
      setAnalysis(res.data);
    } catch { setSnackbar({ open: true, message: '加载失败', severity: 'error' }); }
  };

  const industryData = report?.industry_exposure
    ? Object.entries(report.industry_exposure).map(([name, value]) => ({ name, value: value * 100 }))
    : [];

  const styleData = report?.style_exposure
    ? Object.entries(report.style_exposure).map(([name, value]) => ({ name, value }))
    : [];

  const metricCard = (label: string, value: string | number, color?: string) => (
    <Paper sx={{ p: 2, textAlign: 'center' }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="h6" sx={{ fontWeight: 700, color: color || 'text.primary' }}>
        {typeof value === 'number' ? value.toFixed(4) : value}
      </Typography>
    </Paper>
  );

  return (
    <Box>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 3 }}>绩效分析</Typography>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField label="选择回测" select size="small" value={selectedBacktest} onChange={(e) => setSelectedBacktest(e.target.value)} sx={{ minWidth: 200 }}>
            {backtests.map((b) => <MenuItem key={b.id} value={b.id}>{b.name} (#{b.id})</MenuItem>)}
          </TextField>
          <Button variant="contained" startIcon={<AssessmentIcon />} onClick={handleGenerate}>生成报告</Button>
          <Button variant="outlined" onClick={handleLoadAnalysis}>加载分析</Button>
        </Box>
      </Paper>

      {analysis && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>绩效指标</Typography>
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('总收益', analysis.total_return, analysis.total_return >= 0 ? '#66bb6a' : '#ef5350')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('年化收益', analysis.annual_return, analysis.annual_return >= 0 ? '#66bb6a' : '#ef5350')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('基准收益', analysis.benchmark_return)}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('超额收益', analysis.excess_return)}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('最大回撤', analysis.max_drawdown, '#ef5350')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('夏普比率', analysis.sharpe_ratio)}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('卡玛比率', analysis.calmar_ratio)}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('信息比率', analysis.information_ratio ?? '-')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('索提诺比率', analysis.sortino_ratio ?? '-')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('波动率', analysis.volatility ?? '-')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('胜率', analysis.win_rate != null ? `${(analysis.win_rate * 100).toFixed(1)}%` : '-')}</Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}>{metricCard('盈亏比', analysis.profit_loss_ratio ?? '-')}</Grid>
          </Grid>
        </Box>
      )}

      {report && (
        <Grid container spacing={3}>
          {industryData.length > 0 && (
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>行业暴露</Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={industryData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}>
                      {industryData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
          )}
          {styleData.length > 0 && (
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>风格暴露</Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={styleData} cx="50%" cy="50%" outerRadius={80}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="name" fontSize={12} />
                    <PolarRadiusAxis fontSize={10} />
                    <Radar name="暴露度" dataKey="value" stroke="#4fc3f7" fill="#4fc3f7" fillOpacity={0.3} />
                    <Legend />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
          )}
        </Grid>
      )}

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
