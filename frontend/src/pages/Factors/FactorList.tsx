import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, IconButton, Dialog, DialogTitle,
  DialogContent, DialogActions, TextField, MenuItem, Snackbar, Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { factorApi, Factor, FactorCreate } from '../../api/factors';

const CATEGORIES = ['value', 'growth', 'quality', 'momentum', 'volatility', 'liquidity', 'technical'];
const DIRECTIONS = ['desc', 'asc'];

export default function FactorList() {
  const navigate = useNavigate();
  const [factors, setFactors] = useState<Factor[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });
  const [form, setForm] = useState<FactorCreate>({
    factor_code: '',
    factor_name: '',
    category: 'value',
    direction: 'desc',
    calc_expression: '',
    description: '',
  });

  const loadFactors = async () => {
    try {
      const res = await factorApi.list({ limit: 200 });
      setFactors(res.data);
    } catch {
      setSnackbar({ open: true, message: '加载因子列表失败', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadFactors(); }, []);

  const handleCreate = async () => {
    try {
      await factorApi.create(form);
      setDialogOpen(false);
      setForm({ factor_code: '', factor_name: '', category: 'value', direction: 'desc', calc_expression: '', description: '' });
      setSnackbar({ open: true, message: '因子创建成功', severity: 'success' });
      loadFactors();
    } catch {
      setSnackbar({ open: true, message: '创建失败', severity: 'error' });
    }
  };

  const categoryColor: Record<string, 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info' | 'default'> = {
    value: 'primary', growth: 'success', quality: 'warning', momentum: 'error',
    volatility: 'secondary', liquidity: 'info', technical: 'default',
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>因子管理</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
          新建因子
        </Button>
      </Box>

      {loading ? <Typography>加载中...</Typography> : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>因子代码</TableCell>
                <TableCell>因子名称</TableCell>
                <TableCell>分类</TableCell>
                <TableCell>方向</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>更新时间</TableCell>
                <TableCell>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {factors.map((f) => (
                <TableRow key={f.id} hover>
                  <TableCell>{f.id}</TableCell>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{f.factor_code}</TableCell>
                  <TableCell>{f.factor_name}</TableCell>
                  <TableCell><Chip label={f.category} size="small" color={categoryColor[f.category] || 'default'} /></TableCell>
                  <TableCell>{f.direction === 'desc' ? '越大越好' : '越小越好'}</TableCell>
                  <TableCell><Chip label={f.is_active ? '启用' : '停用'} size="small" color={f.is_active ? 'success' : 'default'} /></TableCell>
                  <TableCell>{f.updated_at?.slice(0, 10)}</TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => navigate(`/factors/${f.id}`)}>
                      <VisibilityIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
              {factors.length === 0 && (
                <TableRow><TableCell colSpan={8} align="center">暂无因子数据</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>新建因子</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField label="因子代码" value={form.factor_code} onChange={(e) => setForm({ ...form, factor_code: e.target.value })} fullWidth required />
          <TextField label="因子名称" value={form.factor_name} onChange={(e) => setForm({ ...form, factor_name: e.target.value })} fullWidth required />
          <TextField label="分类" select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} fullWidth>
            {CATEGORIES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
          </TextField>
          <TextField label="方向" select value={form.direction} onChange={(e) => setForm({ ...form, direction: e.target.value })} fullWidth>
            {DIRECTIONS.map((d) => <MenuItem key={d} value={d}>{d === 'desc' ? '越大越好' : '越小越好'}</MenuItem>)}
          </TextField>
          <TextField label="计算表达式" value={form.calc_expression} onChange={(e) => setForm({ ...form, calc_expression: e.target.value })} fullWidth required multiline rows={2} />
          <TextField label="描述" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} fullWidth multiline rows={2} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleCreate}>创建</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
