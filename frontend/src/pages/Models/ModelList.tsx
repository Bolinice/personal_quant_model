import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, IconButton, Dialog, DialogTitle,
  DialogContent, DialogActions, TextField, MenuItem, Snackbar, Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { modelApi, Model, ModelCreate } from '../../api/models';

const MODEL_TYPES = ['factor', 'timing', 'portfolio'];

export default function ModelList() {
  const navigate = useNavigate();
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });
  const [form, setForm] = useState<ModelCreate>({ model_name: '', model_type: 'factor', description: '' });

  const loadModels = async () => {
    try {
      const res = await modelApi.list({ limit: 200 });
      setModels(res.data);
    } catch { setSnackbar({ open: true, message: '加载模型列表失败', severity: 'error' }); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadModels(); }, []);

  const handleCreate = async () => {
    try {
      await modelApi.create(form);
      setDialogOpen(false);
      setForm({ model_name: '', model_type: 'factor', description: '' });
      setSnackbar({ open: true, message: '模型创建成功', severity: 'success' });
      loadModels();
    } catch { setSnackbar({ open: true, message: '创建失败', severity: 'error' }); }
  };

  const typeLabel: Record<string, string> = { factor: '多因子', timing: '择时', portfolio: '组合' };
  const typeColor: Record<string, 'primary' | 'secondary' | 'success'> = { factor: 'primary', timing: 'secondary', portfolio: 'success' };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>模型管理</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>新建模型</Button>
      </Box>

      {loading ? <Typography>加载中...</Typography> : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>模型名称</TableCell>
                <TableCell>类型</TableCell>
                <TableCell>版本</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>描述</TableCell>
                <TableCell>更新时间</TableCell>
                <TableCell>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {models.map((m) => (
                <TableRow key={m.id} hover>
                  <TableCell>{m.id}</TableCell>
                  <TableCell>{m.model_name}</TableCell>
                  <TableCell><Chip label={typeLabel[m.model_type] || m.model_type} size="small" color={typeColor[m.model_type]} /></TableCell>
                  <TableCell>{m.version}</TableCell>
                  <TableCell><Chip label={m.status === 'active' ? '启用' : m.status} size="small" color={m.status === 'active' ? 'success' : 'default'} /></TableCell>
                  <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.description || '-'}</TableCell>
                  <TableCell>{m.updated_at?.slice(0, 10)}</TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => navigate(`/models/${m.id}`)}><VisibilityIcon fontSize="small" /></IconButton>
                  </TableCell>
                </TableRow>
              ))}
              {models.length === 0 && <TableRow><TableCell colSpan={8} align="center">暂无模型数据</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>新建模型</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField label="模型名称" value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} fullWidth required />
          <TextField label="模型类型" select value={form.model_type} onChange={(e) => setForm({ ...form, model_type: e.target.value })} fullWidth>
            {MODEL_TYPES.map((t) => <MenuItem key={t} value={t}>{typeLabel[t]}</MenuItem>)}
          </TextField>
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
