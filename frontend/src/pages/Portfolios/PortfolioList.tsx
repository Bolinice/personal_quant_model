import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  MenuItem,
  Snackbar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { portfolioApi } from '@/api';
import type { Portfolio } from '@/api';
import { modelApi } from '@/api';
import type { Model } from '@/api';
import { PageHeader, GlassPanel, GlassTable, NeonChip } from '@/components/ui';
import { useRequireAuth } from '@/hooks/useRequireAuth';

export default function PortfolioList() {
  const navigate = useNavigate();
  const { requireAuth } = useRequireAuth();
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [tradeDate, setTradeDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });
  const [genDialog, setGenDialog] = useState(false);
  const [genModel, setGenModel] = useState('');
  const [genDate, setGenDate] = useState(new Date().toISOString().slice(0, 10));

  useEffect(() => {
    modelApi
      .list({ limit: 200 })
      .then((res) => setModels(res.data))
      .catch(() => {});
  }, []);

  const loadPortfolios = async () => {
    if (!selectedModel) return;
    try {
      const res = await portfolioApi.list(Number(selectedModel), tradeDate || undefined);
      setPortfolios(res.data);
    } catch {
      setSnackbar({ open: true, message: '加载组合失败', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedModel) loadPortfolios();
  }, [selectedModel]);

  const handleGenerate = async () => {
    if (!requireAuth()) return;

    try {
      await portfolioApi.generate(Number(genModel), genDate);
      setGenDialog(false);
      setSnackbar({ open: true, message: '组合生成成功', severity: 'success' });
      if (genModel === selectedModel) loadPortfolios();
    } catch {
      setSnackbar({ open: true, message: '生成失败', severity: 'error' });
    }
  };

  return (
    <Box>
      <PageHeader
        title="组合管理"
        actions={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => {
              if (!requireAuth()) return;
              setGenDialog(true);
            }}
          >
            生成组合
          </Button>
        }
      />

      <GlassPanel sx={{ mb: 3 }}>
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
            label="交易日期"
            type="date"
            size="small"
            value={tradeDate}
            onChange={(e) => setTradeDate(e.target.value)}
          />
          <Button variant="outlined" onClick={loadPortfolios}>
            查询
          </Button>
        </Box>
      </GlassPanel>

      {loading ? (
        <Typography>请选择模型查询组合</Typography>
      ) : (
        <GlassTable>
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>组合代码</TableCell>
              <TableCell>组合名称</TableCell>
              <TableCell>初始资金</TableCell>
              <TableCell>当前市值</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>创建时间</TableCell>
              <TableCell>操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {portfolios.map((p) => (
              <TableRow key={p.id} hover>
                <TableCell>{p.id}</TableCell>
                <TableCell sx={{ fontFamily: 'monospace' }}>{p.portfolio_code}</TableCell>
                <TableCell>{p.portfolio_name}</TableCell>
                <TableCell>{p.initial_capital?.toLocaleString()}</TableCell>
                <TableCell>{p.current_value?.toLocaleString()}</TableCell>
                <TableCell>
                  <NeonChip
                    label={p.is_active ? '活跃' : '停用'}
                    size="small"
                    neonColor={p.is_active ? 'green' : 'default'}
                  />
                </TableCell>
                <TableCell>{p.created_at?.slice(0, 10)}</TableCell>
                <TableCell>
                  <Button size="small" onClick={() => navigate(`/app/portfolios/${p.id}`)}>
                    详情
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {portfolios.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  暂无组合数据
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </GlassTable>
      )}

      <Dialog open={genDialog} onClose={() => setGenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>生成组合</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label="模型"
            select
            size="small"
            value={genModel}
            onChange={(e) => setGenModel(e.target.value)}
          >
            {models.map((m) => (
              <MenuItem key={m.id} value={m.id}>
                {m.model_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="交易日期"
            type="date"
            size="small"
            value={genDate}
            onChange={(e) => setGenDate(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setGenDialog(false)}>取消</Button>
          <Button variant="contained" onClick={handleGenerate}>
            生成
          </Button>
        </DialogActions>
      </Dialog>

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
