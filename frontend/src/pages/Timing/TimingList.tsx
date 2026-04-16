import { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Button, TextField, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Chip, Snackbar, Alert, MenuItem,
} from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import SettingsIcon from '@mui/icons-material/Settings';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { timingApi, TimingSignal, TimingConfig } from '../../api/timing';
import { modelApi, Model } from '../../api/models';

export default function TimingList() {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [signals, setSignals] = useState<TimingSignal[]>([]);
  const [config, setConfig] = useState<TimingConfig | null>(null);
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10));
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });
  const [configForm, setConfigForm] = useState({ config_type: 'ma_timing', config_value: '{}' });

  useEffect(() => {
    modelApi.list({ limit: 200 }).then((res) => setModels(res.data)).catch(() => {});
  }, []);

  const loadSignals = async () => {
    if (!selectedModel || !dateRange.start || !dateRange.end) return;
    try {
      const res = await timingApi.getSignals(Number(selectedModel), dateRange.start, dateRange.end);
      setSignals(res.data);
    } catch { setSnackbar({ open: true, message: '加载信号失败', severity: 'error' }); }
  };

  const loadConfig = async () => {
    if (!selectedModel) return;
    try {
      const res = await timingApi.getConfig(Number(selectedModel));
      setConfig(res.data);
      setConfigForm({ config_type: res.data.config_type, config_value: res.data.config_value });
    } catch { setConfig(null); }
  };

  useEffect(() => {
    if (selectedModel) { loadConfig(); loadSignals(); }
  }, [selectedModel]);

  const handleCalculateSignal = async (type: 'ma' | 'breadth' | 'volatility') => {
    if (!selectedModel) return;
    try {
      const fn = type === 'ma' ? timingApi.calculateMa : type === 'breadth' ? timingApi.calculateBreadth : timingApi.calculateVolatility;
      await fn(Number(selectedModel), tradeDate);
      setSnackbar({ open: true, message: '信号计算完成', severity: 'success' });
      loadSignals();
    } catch { setSnackbar({ open: true, message: '信号计算失败', severity: 'error' }); }
  };

  const handleSaveConfig = async () => {
    if (!selectedModel) return;
    try {
      if (config) {
        await timingApi.updateConfig(Number(selectedModel), configForm);
      } else {
        await timingApi.createConfig({ model_id: Number(selectedModel), ...configForm });
      }
      setSnackbar({ open: true, message: '配置保存成功', severity: 'success' });
      loadConfig();
    } catch { setSnackbar({ open: true, message: '保存失败', severity: 'error' }); }
  };

  const signalChartData = signals.map((s) => ({
    date: s.trade_date?.slice(0, 10) || '',
    exposure: s.exposure,
    signal: s.signal_type === 'long' ? 1 : s.signal_type === 'short' ? -1 : 0,
  }));

  const signalColor: Record<string, 'success' | 'error' | 'default'> = { long: 'success', short: 'error', neutral: 'default' };
  const signalLabel: Record<string, string> = { long: '做多', short: '做空', neutral: '中性' };

  return (
    <Box>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 3 }}>择时管理</Typography>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>选择模型</Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField label="模型" select size="small" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} sx={{ minWidth: 200 }}>
            {models.map((m) => <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>)}
          </TextField>
          <TextField label="开始日期" type="date" size="small" value={dateRange.start} onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })} />
          <TextField label="结束日期" type="date" size="small" value={dateRange.end} onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })} />
          <Button variant="outlined" onClick={loadSignals}>查询信号</Button>
        </Box>
      </Paper>

      {selectedModel && (
        <>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>信号计算</Typography>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
              <TextField label="交易日期" type="date" size="small" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
              <Button variant="outlined" startIcon={<TimelineIcon />} onClick={() => handleCalculateSignal('ma')}>MA信号</Button>
              <Button variant="outlined" onClick={() => handleCalculateSignal('breadth')}>宽度信号</Button>
              <Button variant="outlined" onClick={() => handleCalculateSignal('volatility')}>波动率信号</Button>
            </Box>
          </Paper>

          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>仓位信号图</Typography>
            <Box sx={{ height: 350 }}>
              {signalChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={signalChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" fontSize={12} />
                    <YAxis fontSize={12} domain={[0, 1]} />
                    <Tooltip />
                    <ReferenceLine y={0.5} stroke="#666" strokeDasharray="3 3" />
                    <Line type="stepAfter" dataKey="exposure" stroke="#4fc3f7" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>暂无信号数据</Typography>}
            </Box>
          </Paper>

          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>信号列表</Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>日期</TableCell>
                    <TableCell>信号类型</TableCell>
                    <TableCell>仓位比例</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {signals.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell>{s.trade_date?.slice(0, 10)}</TableCell>
                      <TableCell><Chip label={signalLabel[s.signal_type] || s.signal_type} size="small" color={signalColor[s.signal_type]} /></TableCell>
                      <TableCell>{(s.exposure * 100).toFixed(1)}%</TableCell>
                    </TableRow>
                  ))}
                  {signals.length === 0 && <TableRow><TableCell colSpan={3} align="center">暂无信号数据</TableCell></TableRow>}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>择时参数配置</Typography>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
              <TextField label="配置类型" select size="small" value={configForm.config_type} onChange={(e) => setConfigForm({ ...configForm, config_type: e.target.value })} sx={{ minWidth: 200 }}>
                <MenuItem value="ma_timing">MA择时</MenuItem>
                <MenuItem value="breadth_timing">宽度择时</MenuItem>
                <MenuItem value="volatility_timing">波动率择时</MenuItem>
              </TextField>
              <Button variant="contained" startIcon={<SettingsIcon />} onClick={handleSaveConfig}>保存配置</Button>
            </Box>
            <TextField label="配置值 (JSON)" fullWidth multiline rows={4} value={configForm.config_value} onChange={(e) => setConfigForm({ ...configForm, config_value: e.target.value })} sx={{ fontFamily: 'monospace' }} />
          </Paper>
        </>
      )}

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
