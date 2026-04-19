import { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, TextField, MenuItem, Button, Snackbar, Alert,
} from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend } from 'recharts';
import { performanceApi, backtestApi } from '@/api';
import type { PerformanceAnalysis, PerformanceReport } from '@/api';
import type { Backtest } from '@/api';
import { PageHeader, GlassPanel, MetricCard } from '@/components/ui';

const COLORS = ['#22d3ee', '#8b5cf6', '#10b981', '#f59e0b', '#6366f1', '#3b82f6', '#f43f5e', '#94a3b8'];

const chartStyle = {
  contentStyle: { backgroundColor: 'rgba(15,23,42,0.9)', border: '1px solid rgba(148,163,184,0.15)', borderRadius: 8 },
};

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

  return (
    <Box>
      <PageHeader title="绩效分析" />

      <GlassPanel sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField label="选择回测" select size="small" value={selectedBacktest} onChange={(e) => setSelectedBacktest(e.target.value)} sx={{ minWidth: 200 }}>
            {backtests.map((b) => <MenuItem key={b.id} value={b.id}>{b.name} (#{b.id})</MenuItem>)}
          </TextField>
          <Button variant="contained" startIcon={<AssessmentIcon />} onClick={handleGenerate}>生成报告</Button>
          <Button variant="outlined" onClick={handleLoadAnalysis}>加载分析</Button>
        </Box>
      </GlassPanel>

      {analysis && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>绩效指标</Typography>
          <Grid container spacing={2.5}>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="总收益" value={`${(analysis.total_return * 100).toFixed(2)}%`} color={analysis.total_return >= 0 ? '#10b981' : '#f43f5e'} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="年化收益" value={`${(analysis.annual_return * 100).toFixed(2)}%`} color={analysis.annual_return >= 0 ? '#10b981' : '#f43f5e'} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="基准收益" value={`${(analysis.benchmark_return * 100).toFixed(2)}%`} color="#22d3ee" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="超额收益" value={`${(analysis.excess_return * 100).toFixed(2)}%`} color={analysis.excess_return >= 0 ? '#10b981' : '#f43f5e'} /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="最大回撤" value={`${(analysis.max_drawdown * 100).toFixed(2)}%`} color="#f43f5e" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="夏普比率" value={analysis.sharpe_ratio.toFixed(2)} color="#8b5cf6" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="卡玛比率" value={analysis.calmar_ratio.toFixed(2)} color="#3b82f6" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="信息比率" value={(analysis.information_ratio ?? 0).toFixed(2)} color="#6366f1" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="索提诺比率" value={(analysis.sortino_ratio ?? 0).toFixed(2)} color="#22d3ee" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="波动率" value={analysis.volatility != null ? `${(analysis.volatility * 100).toFixed(2)}%` : '-'} color="#94a3b8" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="胜率" value={analysis.win_rate != null ? `${(analysis.win_rate * 100).toFixed(1)}%` : '-'} color="#10b981" /></Grid>
            <Grid size={{ xs: 6, sm: 4, md: 3 }}><MetricCard label="盈亏比" value={(analysis.profit_loss_ratio ?? 0).toFixed(2)} color="#f59e0b" /></Grid>
          </Grid>
        </Box>
      )}

      {report && (
        <Grid container spacing={2.5}>
          {industryData.length > 0 && (
            <Grid size={{ xs: 12, md: 6 }}>
              <GlassPanel>
                <Typography variant="h6" gutterBottom>行业暴露</Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={industryData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}>
                      {industryData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={chartStyle.contentStyle} />
                  </PieChart>
                </ResponsiveContainer>
              </GlassPanel>
            </Grid>
          )}
          {styleData.length > 0 && (
            <Grid size={{ xs: 12, md: 6 }}>
              <GlassPanel>
                <Typography variant="h6" gutterBottom>风格暴露</Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={styleData} cx="50%" cy="50%" outerRadius={80}>
                    <PolarGrid stroke="rgba(148,163,184,0.15)" />
                    <PolarAngleAxis dataKey="name" fontSize={12} tick={{ fill: '#64748b' }} />
                    <PolarRadiusAxis fontSize={10} tick={{ fill: '#64748b' }} />
                    <Radar name="暴露度" dataKey="value" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.2} />
                    <Legend />
                    <Tooltip contentStyle={chartStyle.contentStyle} />
                  </RadarChart>
                </ResponsiveContainer>
              </GlassPanel>
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
