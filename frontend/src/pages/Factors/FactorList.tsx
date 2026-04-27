import React, { useEffect, useState } from 'react';
import {
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Card, CardContent, CardHeader, Chip, TextField, Select, MenuItem,
  FormControl, InputLabel, IconButton, Box, Typography, CircularProgress,
  TablePagination, Tooltip, Alert, Snackbar,
} from '@mui/material';
import { Search as SearchIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import client from '../../api/client';

interface FactorMetadataItem {
  factor_name: string;
  factor_group: string;
  description: string | null;
  direction: number;
  status: string;
  version: string;
  pit_required: boolean;
  coverage_threshold: number;
}

// GROUP_COLORS：为每个因子组分配固定颜色，用于Chip背景色区分
// 颜色选择遵循直觉：价值(金)=低估值，动量(橙)=趋势，波动率(红)=风险，流动性(青)=交易活跃
const GROUP_COLORS: Record<string, string> = {
  'valuation': '#ffc107',
  'growth': '#4caf50',
  'quality': '#2196f3',
  'momentum': '#ff9800',
  'volatility': '#f44336',
  'liquidity': '#00bcd4',
  'northbound': '#9c27b0',
  'expectation': '#e91e63',
  'microstructure': '#3f51b5',
  'policy': '#ff5722',
  'supply_chain': '#cddc39',
  'sentiment': '#e91e63',
  'ashare_specific': '#ffeb3b',
  'interaction': '#00bcd4',
  'earnings_quality': '#66bb6a',
  'smart_money': '#29b6f6',
  'technical': '#ffa726',
  'industry_rotation': '#ef5350',
  'alt_data': '#ffc107',
  'risk_penalty': '#f44336',
};

const GROUP_LABELS: Record<string, string> = {
  'valuation': '价值', 'growth': '成长', 'quality': '质量',
  'momentum': '动量', 'volatility': '波动率', 'liquidity': '流动性',
  'northbound': '北向资金', 'expectation': '分析师预期',
  'microstructure': '微观结构', 'policy': '政策', 'supply_chain': '供应链',
  'sentiment': '情绪', 'ashare_specific': 'A股特有', 'interaction': '交互',
  'earnings_quality': '盈利质量', 'smart_money': '聪明钱',
  'technical': '技术形态', 'industry_rotation': '行业轮动',
  'alt_data': '另类数据', 'risk_penalty': '风险惩罚',
};

const STATUS_LABELS: Record<string, { label: string; color: 'success' | 'warning' | 'default' | 'error' }> = {
  'production': { label: '生产', color: 'success' },
  'candidate': { label: '候选', color: 'warning' },
  'experimental': { label: '实验', color: 'default' },
  'deprecated': { label: '废弃', color: 'error' },
};

export default function FactorList() {
  const [factors, setFactors] = useState<FactorMetadataItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [groupFilter, setGroupFilter] = useState<string>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(20);
  const [errorMsg, setErrorMsg] = useState('');

  const fetchFactors = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      // 使用/factor-metadata而非/factors，因为/factors只返回16个生产因子，
      // 而/factor-metadata返回全部76个因子（含候选/实验/废弃），用于全局因子管理
      const res = await client.get<FactorMetadataItem[]>('/factor-metadata');
      setFactors(Array.isArray(res.data) ? res.data : []);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '网络错误，请检查后端服务';
      console.error('fetchFactors error:', e);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFactors();
  }, []);

  const groups = Array.from(new Set(factors.map(f => f.factor_group))).sort();

  const filteredFactors = factors.filter(f => {
    const matchSearch = !searchText
      || f.factor_name.toLowerCase().includes(searchText.toLowerCase())
      || (f.description || '').includes(searchText);
    const matchGroup = !groupFilter || f.factor_group === groupFilter;
    return matchSearch && matchGroup;
  });

  const pagedFactors = filteredFactors.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage,
  );

  return (
    <Box sx={{ p: 3 }}>
      <Card>
        <CardHeader
          title={
            <Typography variant="h6">
              因子列表 ({filteredFactors.length}/{factors.length})
            </Typography>
          }
          action={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel>因子组筛选</InputLabel>
                <Select
                  value={groupFilter}
                  label="因子组筛选"
                  onChange={e => { setGroupFilter(e.target.value); setPage(0); }}
                >
                  <MenuItem value="">全部</MenuItem>
                  {groups.map(g => (
                    <MenuItem key={g} value={g}>{GROUP_LABELS[g] || g}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                size="small"
                placeholder="搜索因子名称/描述"
                value={searchText}
                onChange={e => { setSearchText(e.target.value); setPage(0); }}
                sx={{ width: 240 }}
                InputProps={{
                  startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
              />
              <Tooltip title="刷新">
                <IconButton onClick={fetchFactors} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </Box>
          }
        />
        <CardContent sx={{ p: 0 }}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 200 }}>因子名称</TableCell>
                  <TableCell sx={{ width: 120 }}>因子组</TableCell>
                  <TableCell>描述</TableCell>
                  <TableCell sx={{ width: 80 }}>方向</TableCell>
                  <TableCell sx={{ width: 80 }}>状态</TableCell>
                  <TableCell sx={{ width: 60 }}>PIT</TableCell>
                  <TableCell sx={{ width: 60 }}>版本</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {loading && factors.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                      <CircularProgress size={24} />
                    </TableCell>
                  </TableRow>
                ) : pagedFactors.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                      暂无数据
                    </TableCell>
                  </TableRow>
                ) : (
                  pagedFactors.map(f => (
                    <TableRow key={f.factor_name} hover>
                      <TableCell>
                        <code style={{ fontSize: 12 }}>{f.factor_name}</code>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={GROUP_LABELS[f.factor_group] || f.factor_group}
                          size="small"
                          sx={{
                            bgcolor: GROUP_COLORS[f.factor_group] || '#9e9e9e',
                            color: '#fff',
                          }}
                        />
                      </TableCell>
                      <TableCell>{f.description || '-'}</TableCell>
                      <TableCell>
                        <Chip
                          label={f.direction === 1 ? '正向' : '反向'}
                          size="small"
                          variant="outlined"
                          color={f.direction === 1 ? 'success' : 'error'}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={STATUS_LABELS[f.status]?.label || f.status}
                          size="small"
                          color={STATUS_LABELS[f.status]?.color || 'default'}
                        />
                      </TableCell>
                      <TableCell>{f.pit_required ? '是' : '-'}</TableCell>
                      <TableCell>{f.version}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={filteredFactors.length}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={e => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            rowsPerPageOptions={[10, 20, 50]}
            labelRowsPerPage="每页行数"
            labelDisplayedRows={({ from, to, count }) => `${from}-${to} / 共 ${count} 个因子`}
          />
        </CardContent>
      </Card>
      <Snackbar
        open={!!errorMsg}
        autoHideDuration={4000}
        onClose={() => setErrorMsg('')}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setErrorMsg('')}>
          {errorMsg}
        </Alert>
      </Snackbar>
    </Box>
  );
}
