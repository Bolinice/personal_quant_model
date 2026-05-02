import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  MenuItem,
  Snackbar,
  Alert,
} from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import SettingsIcon from '@mui/icons-material/Settings';
import ReactECharts from '@/components/charts/ReactEChartsCore';
import { timingApi } from '@/api';
import type { TimingSignal, TimingConfig } from '@/api';
import { modelApi } from '@/api';
import type { Model } from '@/api';
import { PageHeader, GlassPanel, GlassTable, NeonChip } from '@/components/ui';

export default function TimingList() {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [signals, setSignals] = useState<TimingSignal[]>([]);
  const [config, setConfig] = useState<TimingConfig | null>(null);
  const [dateRange, setDateRange] = useState(() => {
    const end = new Date().toISOString().slice(0, 10);
    const start = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
    return { start, end };
  });
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10));
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });
  const [configForm, setConfigForm] = useState({ config_type: 'ma_timing', config_value: '{}' });

  useEffect(() => {
    modelApi
      .list({ limit: 200 })
      .then((res) => setModels(res.data))
      .catch(() => {});
  }, []);

  const loadSignals = async () => {
    if (!selectedModel || !dateRange.start || !dateRange.end) return;
    try {
      const res = await timingApi.getSignals(Number(selectedModel), dateRange.start, dateRange.end);
      setSignals(res.data);
    } catch {
      setSnackbar({ open: true, message: '加载信号失败', severity: 'error' });
    }
  };

  const loadConfig = async () => {
    if (!selectedModel) return;
    try {
      const res = await timingApi.getConfig(Number(selectedModel));
      setConfig(res.data);
      setConfigForm({ config_type: res.data.config_type, config_value: res.data.config_value });
    } catch {
      setConfig(null);
    }
  };

  useEffect(() => {
    if (selectedModel) {
      loadConfig();
      loadSignals();
    }
  }, [selectedModel]);

  const handleCalculateSignal = async (type: 'ma' | 'breadth' | 'volatility') => {
    if (!selectedModel) return;
    try {
      const fn =
        type === 'ma'
          ? timingApi.calculateMa
          : type === 'breadth'
            ? timingApi.calculateBreadth
            : timingApi.calculateVolatility;
      await fn(Number(selectedModel), tradeDate);
      setSnackbar({ open: true, message: '信号计算完成', severity: 'success' });
      loadSignals();
    } catch {
      setSnackbar({ open: true, message: '信号计算失败', severity: 'error' });
    }
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
    } catch {
      setSnackbar({ open: true, message: '保存失败', severity: 'error' });
    }
  };

  const signalChartData = signals.map((s) => ({
    date: s.trade_date?.slice(0, 10) || '',
    exposure: s.exposure,
    signal: s.signal_type === 'long' ? 1 : s.signal_type === 'short' ? -1 : 0,
  }));

  const signalNeonColor: Record<string, 'green' | 'red' | 'default'> = {
    long: 'green',
    short: 'red',
    neutral: 'default',
  };
  const signalLabel: Record<string, string> = { long: '做多', short: '做空', neutral: '中性' };

  return (
    <Box>
      <PageHeader title="择时管理" />

      <GlassPanel sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          选择模型
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            label="模型"
            select
            size="small"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            sx={{ minWidth: 200 }}
          >
            {models.map((m) => (
              <MenuItem key={m.id} value={m.id}>
                {m.model_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="开始日期"
            type="date"
            size="small"
            value={dateRange.start}
            onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
          />
          <TextField
            label="结束日期"
            type="date"
            size="small"
            value={dateRange.end}
            onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
          />
          <Button variant="outlined" onClick={loadSignals}>
            查询信号
          </Button>
        </Box>
      </GlassPanel>

      {selectedModel && (
        <>
          <GlassPanel sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              信号计算
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
              <TextField
                label="交易日期"
                type="date"
                size="small"
                value={tradeDate}
                onChange={(e) => setTradeDate(e.target.value)}
              />
              <Button
                variant="outlined"
                startIcon={<TimelineIcon />}
                onClick={() => handleCalculateSignal('ma')}
              >
                MA信号
              </Button>
              <Button variant="outlined" onClick={() => handleCalculateSignal('breadth')}>
                宽度信号
              </Button>
              <Button variant="outlined" onClick={() => handleCalculateSignal('volatility')}>
                波动率信号
              </Button>
            </Box>
          </GlassPanel>

          <GlassPanel sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              仓位信号图
            </Typography>
            <Box sx={{ height: 350 }}>
              {signalChartData.length > 0 ? (
                <ReactECharts
                  option={{
                    tooltip: {
                      trigger: 'axis',
                      backgroundColor: 'rgba(15,23,42,0.9)',
                      borderColor: 'rgba(148,163,184,0.15)',
                      borderWidth: 1,
                      textStyle: { color: '#e2e8f0' },
                    },
                    grid: { left: 60, right: 40, top: 40, bottom: 40 },
                    xAxis: {
                      type: 'category',
                      data: signalChartData.map(d => d.date),
                      axisLabel: { fontSize: 12, color: '#64748b' },
                      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } },
                    },
                    yAxis: {
                      type: 'value',
                      min: 0,
                      max: 1,
                      axisLabel: { fontSize: 12, color: '#64748b' },
                      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } },
                      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)', type: 'dashed' } },
                    },
                    series: [
                      {
                        type: 'line',
                        data: signalChartData.map(d => d.exposure),
                        step: 'end',
                        lineStyle: { color: '#22d3ee', width: 2 },
                        itemStyle: { color: '#22d3ee' },
                        showSymbol: false,
                        markLine: {
                          silent: true,
                          symbol: 'none',
                          lineStyle: { color: 'rgba(148,163,184,0.3)', type: 'dashed' },
                          data: [{ yAxis: 0.5 }],
                        },
                      },
                    ],
                  }}
                  style={{ height: '100%', width: '100%' }}
                />
              ) : (
                <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                  暂无信号数据
                </Typography>
              )}
            </Box>
          </GlassPanel>

          <GlassPanel sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              信号列表
            </Typography>
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
                      <TableCell>
                        <NeonChip
                          label={signalLabel[s.signal_type] || s.signal_type}
                          size="small"
                          neonColor={signalNeonColor[s.signal_type]}
                        />
                      </TableCell>
                      <TableCell>{(s.exposure * 100).toFixed(1)}%</TableCell>
                    </TableRow>
                  ))}
                  {signals.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3} align="center">
                        暂无信号数据
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </GlassPanel>

          <GlassPanel>
            <Typography variant="h6" gutterBottom>
              择时参数配置
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
              <TextField
                label="配置类型"
                select
                size="small"
                value={configForm.config_type}
                onChange={(e) => setConfigForm({ ...configForm, config_type: e.target.value })}
                sx={{ minWidth: 200 }}
              >
                <MenuItem value="ma_timing">MA择时</MenuItem>
                <MenuItem value="breadth_timing">宽度择时</MenuItem>
                <MenuItem value="volatility_timing">波动率择时</MenuItem>
              </TextField>
              <Button variant="contained" startIcon={<SettingsIcon />} onClick={handleSaveConfig}>
                保存配置
              </Button>
            </Box>
            <TextField
              label="配置值 (JSON)"
              fullWidth
              multiline
              rows={4}
              value={configForm.config_value}
              onChange={(e) => setConfigForm({ ...configForm, config_value: e.target.value })}
              sx={{ fontFamily: 'monospace' }}
            />
          </GlassPanel>
        </>
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
