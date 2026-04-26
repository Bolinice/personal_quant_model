import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { portfolioApi } from '@/api';
import type { PortfolioPosition, RebalanceRecord } from '@/api';
import { PageHeader, GlassPanel, NeonChip } from '@/components/ui';
import { DisclaimerBanner } from '@/components/compliance';

export default function PortfolioDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [rebalances, setRebalances] = useState<RebalanceRecord[]>([]);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    if (id) {
      portfolioApi.getPositions(Number(id)).then((res) => setPositions(res.data)).catch((e) => {
        setSnackbar({ open: true, message: `持仓加载失败: ${e.message}`, severity: 'error' });
      });
      const endDate = new Date().toISOString().slice(0, 10);
      const startDate = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10);
      portfolioApi.getRebalances(Number(id), startDate, endDate).then((res) => setRebalances(res.data)).catch((e) => {
        console.error('调仓记录加载失败:', e.message);
      });
    }
  }, [id]);

  const rebalanceNeonColor: Record<string, 'cyan' | 'purple' | 'amber'> = { scheduled: 'cyan', signal: 'purple', risk: 'amber' };
  const rebalanceTypeLabel: Record<string, string> = { scheduled: '定期', signal: '信号', risk: '风控' };

  return (
    <Box>
      <PageHeader
        title={`组合详情 #${id}`}
        actions={<Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/portfolios')}>返回</Button>}
      />

      <GlassPanel sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>持仓明细</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>证券ID</TableCell>
                <TableCell>数量</TableCell>
                <TableCell>权重</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {positions.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.security_id}</TableCell>
                  <TableCell>{p.quantity?.toLocaleString()}</TableCell>
                  <TableCell>{(p.weight * 100).toFixed(2)}%</TableCell>
                </TableRow>
              ))}
              {positions.length === 0 && <TableRow><TableCell colSpan={3} align="center">暂无持仓数据</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      </GlassPanel>

      <GlassPanel>
        <Typography variant="h6" gutterBottom>调仓记录</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>日期</TableCell>
                <TableCell>类型</TableCell>
                <TableCell>买入</TableCell>
                <TableCell>卖出</TableCell>
                <TableCell>换手率</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rebalances.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.trade_date?.slice(0, 10)}</TableCell>
                  <TableCell><NeonChip label={rebalanceTypeLabel[r.rebalance_type] || r.rebalance_type} size="small" neonColor={rebalanceNeonColor[r.rebalance_type] || 'default'} /></TableCell>
                  <TableCell>{Array.isArray(r.buy_list) ? r.buy_list.length : 0}只</TableCell>
                  <TableCell>{Array.isArray(r.sell_list) ? r.sell_list.length : 0}只</TableCell>
                  <TableCell>{(r.total_turnover * 100).toFixed(2)}%</TableCell>
                </TableRow>
              ))}
              {rebalances.length === 0 && <TableRow><TableCell colSpan={5} align="center">暂无调仓记录</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      </GlassPanel>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>{snackbar.message}</Alert>
      </Snackbar>
      <DisclaimerBanner variant="page" pageType="portfolio" />
    </Box>
  );
}
