import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  IconButton,
  Typography,
  CircularProgress,
  Alert,
  Tooltip,
  Chip,
  Card,
  CardContent,
  CardActions,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import VisibilityIcon from '@mui/icons-material/Visibility';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import TimelineIcon from '@mui/icons-material/Timeline';
import { motion } from 'framer-motion';
import PageHeader from '../../components/ui/PageHeader';
import StatusChip from '../../components/ui/StatusChip';
import { strategyApi } from '../../api/strategies';
import type { Strategy } from '../../api/types/strategies';

export default function StrategyList() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await strategyApi.list();
      console.log('API Response:', response);
      setStrategies(response.items || []);
    } catch (err: any) {
      console.error('Failed to load strategies:', err);
      const errorMessage = err.message || '加载策略列表失败';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('确定要归档这个策略吗？')) {
      try {
        await strategyApi.archive(id);
        loadStrategies();
      } catch (err) {
        console.error('Failed to archive strategy:', err);
        alert('归档失败');
      }
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress sx={{ color: '#22d3ee' }} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert
          severity="error"
          sx={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
          }}
        >
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="策略管理"
        subtitle={`共 ${strategies.length} 个策略`}
        breadcrumbs={[
          { label: '首页', path: '/' },
          { label: '策略管理' },
        ]}
        actions={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => navigate('/app/strategies/new')}
            sx={{
              background: 'linear-gradient(135deg, #22d3ee 0%, #3b82f6 100%)',
              color: '#0f172a',
              fontWeight: 600,
              px: 3,
              py: 1.25,
              borderRadius: '10px',
              textTransform: 'none',
              boxShadow: '0 4px 12px rgba(34, 211, 238, 0.3)',
              '&:hover': {
                background: 'linear-gradient(135deg, #06b6d4 0%, #2563eb 100%)',
                boxShadow: '0 6px 16px rgba(34, 211, 238, 0.4)',
              },
            }}
          >
            新建策略
          </Button>
        }
      />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {/* 卡片网格布局 */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              lg: 'repeat(3, 1fr)',
            },
            gap: 3,
            mt: 3,
          }}
        >
          {strategies.map((strategy, index) => (
            <motion.div
              key={strategy.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.05 }}
            >
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'rgba(15, 23, 42, 0.5)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(148, 163, 184, 0.06)',
                  borderRadius: '16px',
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  '&:hover': {
                    borderColor: 'rgba(34, 211, 238, 0.2)',
                    transform: 'translateY(-4px)',
                    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
                  },
                }}
              >
                <CardContent sx={{ flex: 1, p: 3 }}>
                  {/* 头部：标题 + 状态 */}
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                    <Box sx={{ flex: 1, minWidth: 0, mr: 2 }}>
                      <Typography
                        variant="h6"
                        sx={{
                          color: '#e2e8f0',
                          fontWeight: 600,
                          fontSize: '1.125rem',
                          mb: 0.5,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {strategy.model_name}
                      </Typography>
                      <Typography
                        sx={{
                          color: '#64748b',
                          fontSize: '0.75rem',
                          letterSpacing: '0.05em',
                        }}
                      >
                        ID: {strategy.model_code || 'N/A'}
                      </Typography>
                    </Box>
                    <StatusChip status={strategy.status || 'draft'} />
                  </Box>

                  {/* 描述 */}
                  {strategy.description && (
                    <Typography
                      sx={{
                        color: '#94a3b8',
                        fontSize: '0.875rem',
                        lineHeight: 1.6,
                        mb: 2,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {strategy.description}
                    </Typography>
                  )}

                  {/* 指标网格 */}
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(2, 1fr)',
                      gap: 2,
                      p: 2,
                      borderRadius: '12px',
                      background: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(148, 163, 184, 0.04)',
                    }}
                  >
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                        <ShowChartIcon sx={{ fontSize: 14, color: '#22d3ee' }} />
                        <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                          IC均值
                        </Typography>
                      </Box>
                      <Typography sx={{ fontSize: '1rem', fontWeight: 600, color: '#e2e8f0' }}>
                        {strategy.ic_mean?.toFixed(3) || 'N/A'}
                      </Typography>
                    </Box>
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                        <TimelineIcon sx={{ fontSize: 14, color: '#8b5cf6' }} />
                        <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                          IC标准差
                        </Typography>
                      </Box>
                      <Typography sx={{ fontSize: '1rem', fontWeight: 600, color: '#e2e8f0' }}>
                        {strategy.ic_std?.toFixed(3) || 'N/A'}
                      </Typography>
                    </Box>
                  </Box>

                  {/* 因子标签 */}
                  {strategy.factors && strategy.factors.length > 0 && (
                    <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {strategy.factors.slice(0, 3).map((factor) => (
                        <Chip
                          key={factor.id}
                          label={factor.factor_name}
                          size="small"
                          sx={{
                            backgroundColor: 'rgba(34, 211, 238, 0.06)',
                            color: '#22d3ee',
                            border: '1px solid rgba(34, 211, 238, 0.15)',
                            fontSize: '0.75rem',
                            height: 24,
                          }}
                        />
                      ))}
                      {strategy.factors.length > 3 && (
                        <Chip
                          label={`+${strategy.factors.length - 3}`}
                          size="small"
                          sx={{
                            backgroundColor: 'rgba(148, 163, 184, 0.06)',
                            color: '#94a3b8',
                            border: '1px solid rgba(148, 163, 184, 0.1)',
                            fontSize: '0.75rem',
                            height: 24,
                          }}
                        />
                      )}
                    </Box>
                  )}
                </CardContent>

                {/* 操作按钮 */}
                <CardActions
                  sx={{
                    p: 2,
                    pt: 0,
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: 1,
                  }}
                >
                  <Tooltip title="查看详情">
                    <IconButton
                      size="small"
                      onClick={() => navigate(`/app/strategies/${strategy.id}`)}
                      sx={{
                        color: '#22d3ee',
                        '&:hover': {
                          backgroundColor: 'rgba(34, 211, 238, 0.1)',
                        },
                      }}
                    >
                      <VisibilityIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="编辑">
                    <IconButton
                      size="small"
                      onClick={() => navigate(`/app/strategies/${strategy.id}/edit`)}
                      sx={{
                        color: '#3b82f6',
                        '&:hover': {
                          backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        },
                      }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="归档">
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(strategy.id)}
                      sx={{
                        color: '#94a3b8',
                        '&:hover': {
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          color: '#ef4444',
                        },
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </CardActions>
              </Card>
            </motion.div>
          ))}
        </Box>

        {/* 空状态 */}
        {strategies.length === 0 && (
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
            <TrendingUpIcon sx={{ fontSize: 64, color: '#64748b', mb: 2 }} />
            <Typography sx={{ color: '#94a3b8', fontSize: '1rem', mb: 1 }}>
              暂无策略
            </Typography>
            <Typography sx={{ color: '#64748b', fontSize: '0.875rem' }}>
              点击右上角"新建策略"按钮创建您的第一个策略
            </Typography>
          </Box>
        )}
      </motion.div>
    </Box>
  );
}
