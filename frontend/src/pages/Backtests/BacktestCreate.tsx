import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, TextField, Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { backtestApi } from '@/api';
import type { BacktestCreate } from '@/api';
import { PageHeader, GlassPanel } from '@/components/ui';

export default function BacktestCreate() {
  const navigate = useNavigate();
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });
  const [form, setForm] = useState<BacktestCreate>({
    name: '',
    start_date: '2020-01-01',
    end_date: '2024-12-31',
    initial_capital: 1000000,
    description: '',
  });

  const handleCreate = async () => {
    try {
      const res = await backtestApi.create(form);
      setSnackbar({ open: true, message: '回测创建成功', severity: 'success' });
      setTimeout(() => navigate(`/backtests/${res.data.id}`), 1000);
    } catch { setSnackbar({ open: true, message: '创建失败', severity: 'error' }); }
  };

  return (
    <Box>
      <PageHeader
        title="新建回测"
        actions={<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/backtests')}>返回</Button>}
      />

      <GlassPanel sx={{ maxWidth: 600 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="回测名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} fullWidth required />
          <TextField label="开始日期" type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} fullWidth />
          <TextField label="结束日期" type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} fullWidth />
          <TextField label="初始资金" type="number" value={form.initial_capital} onChange={(e) => setForm({ ...form, initial_capital: Number(e.target.value) })} fullWidth />
          <TextField label="描述" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} fullWidth multiline rows={2} />
          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', mt: 2 }}>
            <Button onClick={() => navigate('/backtests')}>取消</Button>
            <Button variant="contained" onClick={handleCreate}>创建</Button>
          </Box>
        </Box>
      </GlassPanel>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
