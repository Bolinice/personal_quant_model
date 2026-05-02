import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  CircularProgress,
  Tooltip,
  Alert,
  Chip,
  Card,
  CardContent,
} from '@mui/material';
import {
  Search as SearchIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import client from '../../api/client';
import PageHeader from '../../components/ui/PageHeader';
import GlassPanel from '../../components/ui/GlassPanel';

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

const GROUP_COLORS: Record<string, string> = {
  valuation: '#ffc107',
  growth: '#10b981',
  quality: '#3b82f6',
  momentum: '#ff9800',
  volatility: '#ef4444',
  liquidity: '#22d3ee',
  northbound: '#8b5cf6',
  expectation: '#ec4899',
  microstructure: '#6366f1',
  policy: '#f97316',
  supply_chain: '#84cc16',
  sentiment: '#ec4899',
  ashare_specific: '#eab308',
  interaction: '#22d3ee',
  earnings_quality: '#10b981',
  smart_money: '#06b6d4',
  technical: '#fb923c',
  industry_rotation: '#f43f5e',
  alt_data: '#fbbf24',
  risk_penalty: '#ef4444',
};

const GROUP_LABELS: Record<string, string> = {
  valuation: '价值',
  growth: '成长',
  quality: '质量',
  momentum: '动量',
  volatility: '波动率',
  liquidity: '流动性',
  northbound: '北向资金',
  expectation: '分析师预期',
  microstructure: '微观结构',
  policy: '政策',
  supply_chain: '供应链',
  sentiment: '情绪',
  ashare_specific: 'A股特有',
  interaction: '交互',
  earnings_quality: '盈利质量',
  smart_money: '聪明钱',
  technical: '技术形态',
  industry_rotation: '行业轮动',
  alt_data: '另类数据',
  risk_penalty: '风险惩罚',
};

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; bgColor: string }
> = {
  production: { label: '生产', color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.1)' },
  candidate: { label: '候选', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.1)' },
  experimental: { label: '实验', color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.1)' },
  deprecated: { label: '废弃', color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.1)' },
};

export default function FactorList() {
  const [factors, setFactors] = useState<FactorMetadataItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [groupFilter, setGroupFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState('');

  const fetchFactors = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
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

  const groups = Array.from(new Set(factors.map((f) => f.factor_group))).sort();
  const statuses = Array.from(new Set(factors.map((f) => f.status))).sort();

  const filteredFactors = factors.filter((f) => {
    const matchSearch =
      !searchText ||
      f.factor_name.toLowerCase().includes(searchText.toLowerCase()) ||
      (f.description || '').toLowerCase().includes(searchText.toLowerCase());
    const matchGroup = !groupFilter || f.factor_group === groupFilter;
    const matchStatus = !statusFilter || f.status === statusFilter;
    return matchSearch && matchGroup && matchStatus;
  });

  // 按因子组分组
  const groupedFactors = filteredFactors.reduce((acc, factor) => {
    const group = factor.factor_group;
    if (!acc[group]) acc[group] = [];
    acc[group].push(factor);
    return acc;
  }, {} as Record<string, FactorMetadataItem[]>);

  if (loading && factors.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress sx={{ color: '#22d3ee' }} />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="因子库"
        subtitle={`共 ${filteredFactors.length} 个因子 · ${groups.length} 个因子组`}
        breadcrumbs={[
          { label: '首页', path: '/' },
          { label: '因子库' },
        ]}
      />

      {errorMsg && (
        <Alert
          severity="error"
          sx={{
            mb: 3,
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
          }}
          onClose={() => setErrorMsg('')}
        >
          {errorMsg}
        </Alert>
      )}

      {/* 筛选栏 */}
      <GlassPanel sx={{ mb: 3 }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr) auto' },
            gap: 2,
            alignItems: 'center',
          }}
        >
          <TextField
            size="small"
            placeholder="搜索因子名称或描述"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            slotProps={{
              input: {
                startAdornment: <SearchIcon sx={{ mr: 1, color: '#64748b', fontSize: 20 }} />,
              },
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: 'rgba(15, 23, 42, 0.6)',
                '& fieldset': {
                  borderColor: 'rgba(148, 163, 184, 0.1)',
                },
                '&:hover fieldset': {
                  borderColor: 'rgba(148, 163, 184, 0.2)',
                },
                '&.Mui-focused fieldset': {
                  borderColor: '#22d3ee',
                },
              },
            }}
          />
          <FormControl size="small">
            <InputLabel>因子组</InputLabel>
            <Select
              value={groupFilter}
              label="因子组"
              onChange={(e) => setGroupFilter(e.target.value)}
              sx={{
                backgroundColor: 'rgba(15, 23, 42, 0.6)',
                '& fieldset': {
                  borderColor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <MenuItem value="">全部</MenuItem>
              {groups.map((g) => (
                <MenuItem key={g} value={g}>
                  {GROUP_LABELS[g] || g}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small">
            <InputLabel>状态</InputLabel>
            <Select
              value={statusFilter}
              label="状态"
              onChange={(e) => setStatusFilter(e.target.value)}
              sx={{
                backgroundColor: 'rgba(15, 23, 42, 0.6)',
                '& fieldset': {
                  borderColor: 'rgba(148, 163, 184, 0.1)',
                },
              }}
            >
              <MenuItem value="">全部</MenuItem>
              {statuses.map((s) => (
                <MenuItem key={s} value={s}>
                  {STATUS_CONFIG[s]?.label || s}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Tooltip title="刷新">
            <IconButton
              onClick={fetchFactors}
              disabled={loading}
              sx={{
                color: '#22d3ee',
                '&:hover': {
                  backgroundColor: 'rgba(34, 211, 238, 0.1)',
                },
              }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </GlassPanel>

      {/* 因子卡片 - 按组展示 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {filteredFactors.length === 0 ? (
          <Box
            sx={{
              textAlign: 'center',
              py: 8,
              px: 3,
              background: 'rgba(15, 23, 42, 0.5)',
              borderRadius: '16px',
              border: '1px solid rgba(148, 163, 184, 0.06)',
            }}
          >
            <SearchIcon sx={{ fontSize: 64, color: '#64748b', mb: 2 }} />
            <Typography sx={{ color: '#94a3b8', fontSize: '1rem', mb: 1 }}>
              未找到匹配的因子
            </Typography>
            <Typography sx={{ color: '#64748b', fontSize: '0.875rem' }}>
              尝试调整筛选条件或搜索关键词
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {Object.entries(groupedFactors).map(([group, groupFactors]) => (
              <Box key={group}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  <Box
                    sx={{
                      width: 4,
                      height: 24,
                      borderRadius: '2px',
                      background: `linear-gradient(180deg, ${GROUP_COLORS[group] || '#94a3b8'} 0%, transparent 100%)`,
                    }}
                  />
                  <Typography
                    sx={{
                      fontSize: '1.125rem',
                      fontWeight: 600,
                      color: '#e2e8f0',
                    }}
                  >
                    {GROUP_LABELS[group] || group}
                  </Typography>
                  <Chip
                    label={groupFactors.length}
                    size="small"
                    sx={{
                      backgroundColor: 'rgba(148, 163, 184, 0.1)',
                      color: '#94a3b8',
                      fontSize: '0.75rem',
                      height: 20,
                    }}
                  />
                </Box>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: {
                      xs: '1fr',
                      md: 'repeat(2, 1fr)',
                      lg: 'repeat(3, 1fr)',
                    },
                    gap: 2,
                  }}
                >
                  {groupFactors.map((factor, index) => (
                    <motion.div
                      key={factor.factor_name}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: index * 0.03 }}
                    >
                      <Card
                        sx={{
                          height: '100%',
                          background: 'rgba(15, 23, 42, 0.5)',
                          backdropFilter: 'blur(20px)',
                          border: '1px solid rgba(148, 163, 184, 0.06)',
                          borderRadius: '12px',
                          transition: 'all 0.2s',
                          '&:hover': {
                            borderColor: `${GROUP_COLORS[group] || '#22d3ee'}40`,
                            transform: 'translateY(-2px)',
                            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
                          },
                        }}
                      >
                        <CardContent sx={{ p: 2.5 }}>
                          {/* 头部：因子名 + 状态 */}
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
                            <Typography
                              sx={{
                                fontSize: '0.8125rem',
                                fontFamily: '"JetBrains Mono", monospace',
                                fontWeight: 600,
                                color: '#e2e8f0',
                                flex: 1,
                                mr: 1,
                                wordBreak: 'break-all',
                              }}
                            >
                              {factor.factor_name}
                            </Typography>
                            <Chip
                              label={STATUS_CONFIG[factor.status]?.label || factor.status}
                              size="small"
                              sx={{
                                backgroundColor: STATUS_CONFIG[factor.status]?.bgColor || 'rgba(148, 163, 184, 0.1)',
                                color: STATUS_CONFIG[factor.status]?.color || '#94a3b8',
                                fontSize: '0.6875rem',
                                height: 20,
                                fontWeight: 600,
                              }}
                            />
                          </Box>

                          {/* 描述 */}
                          {factor.description && (
                            <Typography
                              sx={{
                                fontSize: '0.8125rem',
                                color: '#94a3b8',
                                lineHeight: 1.5,
                                mb: 2,
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                              }}
                            >
                              {factor.description}
                            </Typography>
                          )}

                          {/* 属性标签 */}
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                            <Chip
                              icon={factor.direction === 1 ? <TrendingUpIcon /> : <TrendingDownIcon />}
                              label={factor.direction === 1 ? '正向' : '反向'}
                              size="small"
                              sx={{
                                backgroundColor: factor.direction === 1 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                                color: factor.direction === 1 ? '#10b981' : '#ef4444',
                                border: `1px solid ${factor.direction === 1 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
                                fontSize: '0.6875rem',
                                height: 24,
                                '& .MuiChip-icon': {
                                  fontSize: 14,
                                },
                              }}
                            />
                            {factor.pit_required && (
                              <Chip
                                icon={<CheckCircleIcon />}
                                label="PIT"
                                size="small"
                                sx={{
                                  backgroundColor: 'rgba(34, 211, 238, 0.1)',
                                  color: '#22d3ee',
                                  border: '1px solid rgba(34, 211, 238, 0.2)',
                                  fontSize: '0.6875rem',
                                  height: 24,
                                  '& .MuiChip-icon': {
                                    fontSize: 14,
                                  },
                                }}
                              />
                            )}
                            <Chip
                              label={`v${factor.version}`}
                              size="small"
                              sx={{
                                backgroundColor: 'rgba(148, 163, 184, 0.1)',
                                color: '#94a3b8',
                                fontSize: '0.6875rem',
                                height: 24,
                              }}
                            />
                          </Box>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </motion.div>
    </Box>
  );
}
