import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, Table, TableBody, TableCell,
  TableHead, TableRow, IconButton, Snackbar, Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { backtestApi } from '@/api';
import type { Backtest } from '@/api';
import { PageHeader, GlassTable, NeonChip } from '@/components/ui';

const statusNeonColor: Record<string, 'default' | 'cyan' | 'green' | 'red' | 'amber'> = {
  pending: 'default', running: 'cyan', completed: 'green', failed: 'red', cancelled: 'amber',
};
const statusLabel: Record<string, string> = {
  pending: '待运行', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消',
};

export default function BacktestList() {
  const navigate = useNavigate();
  const [backtests, setBacktests] = useState<Backtest[]>([]);
  const [loading, setLoading] = useState(true);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  const loadBacktests = async () => {
    try {
      const res = await backtestApi.list({ limit: 200 });
      setBacktests(res.data);
    } catch { setSnackbar({ open: true, message: '加载回测列表失败', severity: 'error' }); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadBacktests(); }, []);

  const handleRun = async (id: number) => {
    try {
      await backtestApi.run(id);
      setSnackbar({ open: true, message: '回测已启动', severity: 'success' });
      loadBacktests();
    } catch { setSnackbar({ open: true, message: '启动失败', severity: 'error' }); }
  };

  return (
    <Box>
      <PageHeader
        title="回测管理"
        actions={<Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate('/backtests/create')}>新建回测</Button>}
      />

      {loading ? <Typography>加载中...</Typography> : (
        <GlassTable>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>名称</TableCell>
                <TableCell>开始日期</TableCell>
                <TableCell>结束日期</TableCell>
                <TableCell>初始资金</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>创建时间</TableCell>
                <TableCell>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {backtests.map((b) => (
                <TableRow key={b.id} hover>
                  <TableCell>{b.id}</TableCell>
                  <TableCell>{b.name}</TableCell>
                  <TableCell>{b.start_date?.slice(0, 10)}</TableCell>
                  <TableCell>{b.end_date?.slice(0, 10)}</TableCell>
                  <TableCell>{b.initial_capital?.toLocaleString()}</TableCell>
                  <TableCell><NeonChip label={statusLabel[b.status] || b.status} size="small" neonColor={statusNeonColor[b.status]} /></TableCell>
                  <TableCell>{b.created_at?.slice(0, 10)}</TableCell>
                  <TableCell>
                    {b.status === 'pending' && (
                      <IconButton size="small" color="success" onClick={() => handleRun(b.id)}><PlayArrowIcon fontSize="small" /></IconButton>
                    )}
                    <IconButton size="small" onClick={() => navigate(`/backtests/${b.id}`)}><VisibilityIcon fontSize="small" /></IconButton>
                  </TableCell>
                </TableRow>
              ))}
              {backtests.length === 0 && <TableRow><TableCell colSpan={8} align="center">暂无回测数据</TableCell></TableRow>}
            </TableBody>
          </Table>
        </GlassTable>
      )}

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
}
