import { useState, useEffect } from 'react';
import {
  Box, Typography, Table, TableBody, TableCell,
  TableHead, TableRow, Snackbar, Alert,
} from '@mui/material';
import { factorApi } from '@/api';
import type { Factor } from '@/api';
import { PageHeader, GlassTable, NeonChip } from '@/components/ui';

const categoryNeonColor: Record<string, 'cyan' | 'green' | 'amber' | 'red' | 'purple' | 'blue' | 'default'> = {
  value: 'cyan', growth: 'green', quality: 'amber', momentum: 'red',
  volatility: 'purple', liquidity: 'blue', technical: 'default',
};

const categoryLabel: Record<string, string> = {
  value: '价值', growth: '成长', quality: '质量', momentum: '动量',
  volatility: '波动率', liquidity: '流动性', technical: '技术',
};

export default function FactorList() {
  const [factors, setFactors] = useState<Factor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    factorApi.list({ limit: 200 })
      .then((res) => setFactors(res.data))
      .catch(() => setError('加载因子列表失败'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Box>
      <PageHeader title="因子管理" />

      {loading ? <Typography>加载中...</Typography> : (
        <GlassTable>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>因子代码</TableCell>
                <TableCell>因子名称</TableCell>
                <TableCell>分类</TableCell>
                <TableCell>方向</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>更新时间</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {factors.map((f) => (
                <TableRow key={f.id} hover>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{f.factor_code}</TableCell>
                  <TableCell>{f.factor_name}</TableCell>
                  <TableCell><NeonChip label={categoryLabel[f.category] || f.category} size="small" neonColor={categoryNeonColor[f.category]} /></TableCell>
                  <TableCell>{f.direction === 'desc' ? '越大越好' : '越小越好'}</TableCell>
                  <TableCell><NeonChip label={f.is_active ? '启用' : '停用'} size="small" neonColor={f.is_active ? 'green' : 'default'} /></TableCell>
                  <TableCell>{f.updated_at?.slice(0, 10)}</TableCell>
                </TableRow>
              ))}
              {factors.length === 0 && <TableRow><TableCell colSpan={6} align="center">暂无因子数据</TableCell></TableRow>}
            </TableBody>
          </Table>
        </GlassTable>
      )}

      <Snackbar open={!!error} autoHideDuration={3000} onClose={() => setError('')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
      <DisclaimerBanner variant="section" pageType="factor" />
    </Box>
  );
}
