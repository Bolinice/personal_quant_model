import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Grid, Button, TextField, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Tabs, Tab, MenuItem, Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CalculateIcon from '@mui/icons-material/Calculate';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { factorApi } from '@/api';
import type { Factor, FactorAnalysis } from '@/api';
import { PageHeader, GlassPanel, GlassTable, NeonChip } from '@/components/ui';

export default function FactorDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [factor, setFactor] = useState<Factor | null>(null);
  const [tab, setTab] = useState(0);
  const [analyses, setAnalyses] = useState<FactorAnalysis[]>([]);
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10));
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    if (id) {
      factorApi.get(Number(id)).then((res) => setFactor(res.data)).catch(() => navigate('/factors'));
    }
  }, [id]);

  const handleCalculate = async () => {
    try {
      await factorApi.calculate(Number(id), tradeDate);
      setSnackbar({ open: true, message: '因子值计算已触发', severity: 'success' });
    } catch { setSnackbar({ open: true, message: '计算失败', severity: 'error' }); }
  };

  const handlePreprocess = async () => {
    try {
      await factorApi.preprocess(Number(id), tradeDate);
      setSnackbar({ open: true, message: '预处理已触发', severity: 'success' });
    } catch { setSnackbar({ open: true, message: '预处理失败', severity: 'error' }); }
  };

  const handleIcAnalysis = async () => {
    try {
      await factorApi.icAnalysis(Number(id), dateRange.start, dateRange.end);
      const res = await factorApi.getAnalysis(Number(id), dateRange.start, dateRange.end);
      setAnalyses(res.data);
      setSnackbar({ open: true, message: 'IC分析完成', severity: 'success' });
    } catch { setSnackbar({ open: true, message: 'IC分析失败', severity: 'error' }); }
  };

  const handleGroupReturns = async () => {
    try {
      await factorApi.groupReturns(Number(id), dateRange.start, dateRange.end);
      const res = await factorApi.getAnalysis(Number(id), dateRange.start, dateRange.end);
      setAnalyses(res.data);
      setSnackbar({ open: true, message: '分组收益分析完成', severity: 'success' });
    } catch { setSnackbar({ open: true, message: '分组收益分析失败', severity: 'error' }); }
  };

  const loadAnalysis = async () => {
    if (id && dateRange.start && dateRange.end) {
      try {
        const res = await factorApi.getAnalysis(Number(id), dateRange.start, dateRange.end);
        setAnalyses(res.data);
      } catch { /* ignore */ }
    }
  };

  const icChartData = analyses
    .filter((a) => a.ic !== null)
    .map((a) => ({ date: a.analysis_date?.slice(0, 10) || '', IC: a.ic, RankIC: a.rank_ic }));

  const groupReturnData = analyses
    .filter((a) => a.group_returns && a.group_returns.length > 0)
    .flatMap((a) => {
      const groups = a.group_returns!;
      return groups.map((ret, i) => ({ group: `G${i + 1}`, return: ret, date: a.analysis_date?.slice(0, 10) || '' }));
    });

  if (!factor) return <Typography>加载中...</Typography>;

  return (
    <Box>
      <PageHeader
        title={factor.factor_name}
        actions={
          <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/factors')}>返回</Button>
        }
      />
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <NeonChip label={factor.category} size="small" neonColor="cyan" />
        <NeonChip label={factor.is_active ? '启用' : '停用'} size="small" neonColor={factor.is_active ? 'green' : 'default'} />
      </Box>

      <GlassPanel sx={{ mb: 3 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">因子代码</Typography><Typography sx={{ fontFamily: 'monospace' }}>{factor.factor_code}</Typography></Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">方向</Typography><Typography>{factor.direction === 'desc' ? '越大越好' : '越小越好'}</Typography></Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">计算表达式</Typography><Typography sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{factor.calc_expression}</Typography></Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">描述</Typography><Typography>{factor.description || '-'}</Typography></Grid>
        </Grid>
      </GlassPanel>

      <GlassPanel sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>因子操作</Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField label="交易日期" type="date" size="small" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
          <Button variant="outlined" startIcon={<CalculateIcon />} onClick={handleCalculate}>计算因子值</Button>
          <Button variant="outlined" startIcon={<AutoFixHighIcon />} onClick={handlePreprocess}>预处理</Button>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mt: 2, flexWrap: 'wrap' }}>
          <TextField label="开始日期" type="date" size="small" value={dateRange.start} onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })} />
          <TextField label="结束日期" type="date" size="small" value={dateRange.end} onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })} />
          <Button variant="outlined" startIcon={<AnalyticsIcon />} onClick={handleIcAnalysis}>IC分析</Button>
          <Button variant="outlined" onClick={handleGroupReturns}>分组收益</Button>
          <Button variant="text" onClick={loadAnalysis}>加载历史分析</Button>
        </Box>
      </GlassPanel>

      <GlassPanel>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="IC分析" />
          <Tab label="分组收益" />
          <Tab label="分析数据" />
        </Tabs>

        {tab === 0 && (
          <Box sx={{ mt: 2, height: 400 }}>
            {icChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={icChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                  <XAxis dataKey="date" fontSize={12} tick={{ fill: '#64748b' }} />
                  <YAxis fontSize={12} tick={{ fill: '#64748b' }} />
                  <Tooltip contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', border: '1px solid rgba(148,163,184,0.15)', borderRadius: 8 }} />
                  <Line type="monotone" dataKey="IC" stroke="#22d3ee" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="RankIC" stroke="#8b5cf6" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            ) : <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>暂无IC分析数据，请先运行IC分析</Typography>}
          </Box>
        )}

        {tab === 1 && (
          <Box sx={{ mt: 2, height: 400 }}>
            {groupReturnData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={groupReturnData.filter((_, i) => i < 10)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                  <XAxis dataKey="group" fontSize={12} tick={{ fill: '#64748b' }} />
                  <YAxis fontSize={12} tick={{ fill: '#64748b' }} />
                  <Tooltip contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', border: '1px solid rgba(148,163,184,0.15)', borderRadius: 8 }} />
                  <Bar dataKey="return" fill="#22d3ee" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>暂无分组收益数据，请先运行分组收益分析</Typography>}
          </Box>
        )}

        {tab === 2 && (
          <TableContainer sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>日期</TableCell>
                  <TableCell>类型</TableCell>
                  <TableCell>IC</TableCell>
                  <TableCell>RankIC</TableCell>
                  <TableCell>均值</TableCell>
                  <TableCell>标准差</TableCell>
                  <TableCell>覆盖率</TableCell>
                  <TableCell>多空收益</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {analyses.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>{a.analysis_date?.slice(0, 10)}</TableCell>
                    <TableCell>{a.analysis_type}</TableCell>
                    <TableCell>{a.ic?.toFixed(4)}</TableCell>
                    <TableCell>{a.rank_ic?.toFixed(4)}</TableCell>
                    <TableCell>{a.mean?.toFixed(4)}</TableCell>
                    <TableCell>{a.std?.toFixed(4)}</TableCell>
                    <TableCell>{a.coverage?.toFixed(2)}%</TableCell>
                    <TableCell>{a.long_short_return?.toFixed(4)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </GlassPanel>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
