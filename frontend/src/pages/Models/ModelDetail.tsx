import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Paper, Grid, Button, TextField, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Chip, Snackbar, Alert, Tabs, Tab, MenuItem,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CalculateIcon from '@mui/icons-material/Calculate';
import SaveIcon from '@mui/icons-material/Save';
import { modelApi, Model, ModelFactorWeight, ModelScore } from '../../api/models';
import { factorApi, Factor } from '../../api/factors';

export default function ModelDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [model, setModel] = useState<Model | null>(null);
  const [tab, setTab] = useState(0);
  const [weights, setWeights] = useState<ModelFactorWeight[]>([]);
  const [factors, setFactors] = useState<Factor[]>([]);
  const [scores, setScores] = useState<ModelScore[]>([]);
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10));
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });
  const [newWeightFactorId, setNewWeightFactorId] = useState('');
  const [newWeightValue, setNewWeightValue] = useState(1.0);

  useEffect(() => {
    if (id) {
      modelApi.get(Number(id)).then((res) => setModel(res.data)).catch(() => navigate('/models'));
      modelApi.getFactorWeights(Number(id)).then((res) => setWeights(res.data)).catch(() => {});
      factorApi.list({ limit: 200 }).then((res) => setFactors(res.data)).catch(() => {});
    }
  }, [id]);

  const handleCalculateScores = async () => {
    try {
      const res = await modelApi.calculateScores(Number(id), tradeDate);
      setScores(res.data);
      setSnackbar({ open: true, message: '模型打分完成', severity: 'success' });
    } catch { setSnackbar({ open: true, message: '打分失败', severity: 'error' }); }
  };

  const handleLoadScores = async () => {
    try {
      const res = await modelApi.getScores(Number(id), tradeDate);
      setScores(res.data);
    } catch { /* ignore */ }
  };

  const handleSaveWeights = async () => {
    try {
      const data = weights.map((w) => ({ factor_id: w.factor_id, weight: w.weight }));
      await modelApi.updateFactorWeights(Number(id), data);
      setSnackbar({ open: true, message: '权重保存成功', severity: 'success' });
    } catch { setSnackbar({ open: true, message: '保存失败', severity: 'error' }); }
  };

  const handleAddWeight = () => {
    if (!newWeightFactorId) return;
    const fid = Number(newWeightFactorId);
    if (weights.some((w) => w.factor_id === fid)) return;
    setWeights([...weights, { id: 0, model_id: Number(id), factor_id: fid, weight: newWeightValue, created_at: '' }]);
    setNewWeightFactorId('');
    setNewWeightValue(1.0);
  };

  const handleRemoveWeight = (factorId: number) => {
    setWeights(weights.filter((w) => w.factor_id !== factorId));
  };

  const handleWeightChange = (factorId: number, value: number) => {
    setWeights(weights.map((w) => w.factor_id === factorId ? { ...w, weight: value } : w));
  };

  const factorName = (factorId: number) => factors.find((f) => f.id === factorId)?.factor_name || `因子${factorId}`;

  if (!model) return <Typography>加载中...</Typography>;

  const typeLabel: Record<string, string> = { factor: '多因子', timing: '择时', portfolio: '组合' };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/models')}>返回</Button>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>{model.model_name}</Typography>
        <Chip label={typeLabel[model.model_type] || model.model_type} color="primary" size="small" />
        <Chip label={`v${model.version}`} size="small" />
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">模型ID</Typography><Typography>{model.id}</Typography></Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">类型</Typography><Typography>{typeLabel[model.model_type]}</Typography></Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">状态</Typography><Chip label={model.status === 'active' ? '启用' : model.status} size="small" color={model.status === 'active' ? 'success' : 'default'} /></Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}><Typography variant="body2" color="text.secondary">描述</Typography><Typography>{model.description || '-'}</Typography></Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="因子权重" />
          <Tab label="模型打分" />
        </Tabs>

        {tab === 0 && (
          <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
              <TextField label="选择因子" select size="small" value={newWeightFactorId} onChange={(e) => setNewWeightFactorId(e.target.value)} sx={{ minWidth: 200 }}>
                {factors.filter((f) => !weights.some((w) => w.factor_id === f.id)).map((f) => (
                  <MenuItem key={f.id} value={f.id}>{f.factor_name} ({f.factor_code})</MenuItem>
                ))}
              </TextField>
              <TextField label="权重" type="number" size="small" value={newWeightValue} onChange={(e) => setNewWeightValue(Number(e.target.value))} sx={{ width: 120 }} />
              <Button variant="outlined" onClick={handleAddWeight}>添加</Button>
              <Box sx={{ flex: 1 }} />
              <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSaveWeights}>保存权重</Button>
            </Box>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>因子ID</TableCell>
                    <TableCell>因子名称</TableCell>
                    <TableCell>权重</TableCell>
                    <TableCell>操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {weights.map((w) => (
                    <TableRow key={w.factor_id}>
                      <TableCell>{w.factor_id}</TableCell>
                      <TableCell>{factorName(w.factor_id)}</TableCell>
                      <TableCell>
                        <TextField type="number" size="small" value={w.weight} onChange={(e) => handleWeightChange(w.factor_id, Number(e.target.value))} variant="standard" sx={{ width: 100 }} />
                      </TableCell>
                      <TableCell><Button size="small" color="error" onClick={() => handleRemoveWeight(w.factor_id)}>删除</Button></TableCell>
                    </TableRow>
                  ))}
                  {weights.length === 0 && <TableRow><TableCell colSpan={4} align="center">暂无因子权重</TableCell></TableRow>}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {tab === 1 && (
          <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
              <TextField label="交易日期" type="date" size="small" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
              <Button variant="contained" startIcon={<CalculateIcon />} onClick={handleCalculateScores}>运行打分</Button>
              <Button variant="outlined" onClick={handleLoadScores}>加载打分结果</Button>
            </Box>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>证券ID</TableCell>
                    <TableCell>综合得分</TableCell>
                    <TableCell>交易日期</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {scores.slice(0, 100).map((s) => (
                    <TableRow key={s.id}>
                      <TableCell>{s.security_id}</TableCell>
                      <TableCell>{s.total_score.toFixed(4)}</TableCell>
                      <TableCell>{s.trade_date?.slice(0, 10)}</TableCell>
                    </TableRow>
                  ))}
                  {scores.length === 0 && <TableRow><TableCell colSpan={3} align="center">暂无打分数据</TableCell></TableRow>}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </Paper>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
