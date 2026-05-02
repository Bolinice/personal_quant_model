import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Alert,
  CircularProgress,
  LinearProgress,
} from '@mui/material';
import {
  Edit as EditIcon,
  Publish as PublishIcon,
  Archive as ArchiveIcon,
  TrendingUp as TrendingUpIcon,
  ShowChart as ShowChartIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { strategyApi } from '../../api/strategies';
import type { Strategy } from '../../api/types/strategies';
import { useRequireAuth } from '../../hooks/useRequireAuth';
import GlassPanel from '../../components/ui/GlassPanel';
import MetricCard from '../../components/ui/MetricCard';
import StatusChip from '../../components/ui/StatusChip';
import PageHeader from '../../components/ui/PageHeader';

export default function StrategyDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { requireAuth } = useRequireAuth();
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      loadStrategy(parseInt(id));
    }
  }, [id]);

  const loadStrategy = async (strategyId: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await strategyApi.get(strategyId);
      setStrategy(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载策略详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    if (requireAuth() && id) {
      navigate(`/app/strategies/${id}/edit`);
    }
  };

  const handlePublish = async () => {
    if (!id || !requireAuth()) return;
    try {
      await strategyApi.publish(parseInt(id));
      loadStrategy(parseInt(id));
    } catch (err: any) {
      setError(err.response?.data?.detail || '发布策略失败');
    }
  };

  const handleArchive = async () => {
    if (!id || !requireAuth()) return;
    if (!window.confirm('确定要归档这个策略吗？')) return;
    try {
      await strategyApi.archive(parseInt(id));
      loadStrategy(parseInt(id));
    } catch (err: any) {
      setError(err.response?.data?.detail || '归档策略失败');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress sx={{ color: '#22d3ee' }} />
      </Box>
    );
  }

  if (error || !strategy) {
    return (
      <Box>
        <Alert
          severity="error"
          sx={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
          }}
        >
          {error || '策略不存在'}
        </Alert>
        <Button
          onClick={() => navigate('/app/strategies')}
          sx={{
            mt: 2,
            color: '#22d3ee',
            '&:hover': { backgroundColor: 'rgba(34, 211, 238, 0.1)' },
          }}
        >
          返回列表
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title={strategy.model_name}
        subtitle={`策略代码: ${strategy.model_code} · 版本: ${strategy.version || 'v1.0'}`}
        breadcrumbs={[
          { label: '首页', path: '/' },
          { label: '策略管理', path: '/app/strategies' },
          { label: strategy.model_name },
        ]}
        actions={
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
            <StatusChip status={strategy.status || 'draft'} />
            {strategy.status === 'draft' && (
              <Button
                variant="contained"
                startIcon={<PublishIcon />}
                onClick={handlePublish}
                sx={{
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  color: '#fff',
                  fontWeight: 600,
                  px: 3,
                  borderRadius: '10px',
                  textTransform: 'none',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                    boxShadow: '0 6px 16px rgba(16, 185, 129, 0.4)',
                  },
                }}
              >
                发布策略
              </Button>
            )}
            {strategy.status === 'active' && (
              <Button
                variant="outlined"
                startIcon={<ArchiveIcon />}
                onClick={handleArchive}
                sx={{
                  borderColor: 'rgba(148, 163, 184, 0.3)',
                  color: '#94a3b8',
                  fontWeight: 600,
                  px: 3,
                  borderRadius: '10px',
                  textTransform: 'none',
                  '&:hover': {
                    borderColor: 'rgba(239, 68, 68, 0.5)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    color: '#ef4444',
                  },
                }}
              >
                归档
              </Button>
            )}
            <Button
              variant="outlined"
              startIcon={<EditIcon />}
              onClick={handleEdit}
              sx={{
                borderColor: 'rgba(34, 211, 238, 0.3)',
                color: '#22d3ee',
                fontWeight: 600,
                px: 3,
                borderRadius: '10px',
                textTransform: 'none',
                '&:hover': {
                  borderColor: 'rgba(34, 211, 238, 0.5)',
                  backgroundColor: 'rgba(34, 211, 238, 0.1)',
                },
              }}
            >
              编辑
            </Button>
          </Box>
        }
      />

      {error && (
        <Alert
          severity="error"
          sx={{
            mb: 3,
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
          }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* 基本信息 */}
          <GlassPanel>
            <Typography
              variant="h6"
              sx={{
                mb: 3,
                fontWeight: 600,
                fontSize: '1.125rem',
                color: '#e2e8f0',
              }}
            >
              基本信息
            </Typography>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: '1fr',
                  sm: 'repeat(2, 1fr)',
                  md: 'repeat(4, 1fr)',
                },
                gap: 3,
              }}
            >
              <Box>
                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    color: '#64748b',
                    mb: 0.5,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  策略代码
                </Typography>
                <Typography
                  sx={{
                    fontSize: '0.9375rem',
                    fontWeight: 600,
                    color: '#e2e8f0',
                  }}
                >
                  {strategy.model_code}
                </Typography>
              </Box>
              <Box>
                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    color: '#64748b',
                    mb: 0.5,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  策略类型
                </Typography>
                <Typography
                  sx={{
                    fontSize: '0.9375rem',
                    fontWeight: 600,
                    color: '#e2e8f0',
                  }}
                >
                  {strategy.model_type}
                </Typography>
              </Box>
              <Box>
                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    color: '#64748b',
                    mb: 0.5,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  版本
                </Typography>
                <Typography
                  sx={{
                    fontSize: '0.9375rem',
                    fontWeight: 600,
                    color: '#e2e8f0',
                  }}
                >
                  {strategy.version || 'v1.0'}
                </Typography>
              </Box>
              <Box>
                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    color: '#64748b',
                    mb: 0.5,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  创建时间
                </Typography>
                <Typography
                  sx={{
                    fontSize: '0.9375rem',
                    fontWeight: 600,
                    color: '#e2e8f0',
                  }}
                >
                  {new Date(strategy.created_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Box>
            {strategy.description && (
              <Box
                sx={{
                  mt: 3,
                  pt: 3,
                  borderTop: '1px solid rgba(148, 163, 184, 0.06)',
                }}
              >
                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    color: '#64748b',
                    mb: 1,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  策略描述
                </Typography>
                <Typography
                  sx={{
                    fontSize: '0.9375rem',
                    color: '#94a3b8',
                    lineHeight: 1.6,
                  }}
                >
                  {strategy.description}
                </Typography>
              </Box>
            )}
          </GlassPanel>

          {/* 性能指标 */}
          {(strategy.ic_mean !== undefined || strategy.ic_ir !== undefined || strategy.ic_std !== undefined) && (
            <Box>
              <Typography
                variant="h6"
                sx={{
                  mb: 2,
                  fontWeight: 600,
                  fontSize: '1.125rem',
                  color: '#e2e8f0',
                }}
              >
                性能指标
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(2, 1fr)',
                    md: 'repeat(3, 1fr)',
                  },
                  gap: 2,
                }}
              >
                {strategy.ic_mean !== undefined && (
                  <GlassPanel>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <ShowChartIcon sx={{ fontSize: 18, color: '#22d3ee' }} />
                      <Typography
                        sx={{
                          fontSize: '0.75rem',
                          color: '#64748b',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                        }}
                      >
                        IC均值
                      </Typography>
                    </Box>
                    <Typography
                      sx={{
                        fontSize: '1.875rem',
                        fontWeight: 700,
                        color: strategy.ic_mean > 0 ? '#10b981' : '#ef4444',
                        mb: 0.5,
                      }}
                    >
                      {strategy.ic_mean.toFixed(4)}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                      {strategy.ic_mean > 0 ? '正向预测能力' : '负向预测能力'}
                    </Typography>
                  </GlassPanel>
                )}
                {strategy.ic_ir !== undefined && (
                  <GlassPanel>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <TrendingUpIcon sx={{ fontSize: 18, color: '#8b5cf6' }} />
                      <Typography
                        sx={{
                          fontSize: '0.75rem',
                          color: '#64748b',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                        }}
                      >
                        IC IR
                      </Typography>
                    </Box>
                    <Typography
                      sx={{
                        fontSize: '1.875rem',
                        fontWeight: 700,
                        color: strategy.ic_ir > 0 ? '#10b981' : '#ef4444',
                        mb: 0.5,
                      }}
                    >
                      {strategy.ic_ir.toFixed(4)}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                      信息比率
                    </Typography>
                  </GlassPanel>
                )}
                {strategy.ic_std !== undefined && (
                  <GlassPanel>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <TimelineIcon sx={{ fontSize: 18, color: '#3b82f6' }} />
                      <Typography
                        sx={{
                          fontSize: '0.75rem',
                          color: '#64748b',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                        }}
                      >
                        IC标准差
                      </Typography>
                    </Box>
                    <Typography
                      sx={{
                        fontSize: '1.875rem',
                        fontWeight: 700,
                        color: '#e2e8f0',
                        mb: 0.5,
                      }}
                    >
                      {strategy.ic_std.toFixed(4)}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                      稳定性指标
                    </Typography>
                  </GlassPanel>
                )}
              </Box>
            </Box>
          )}

          {/* 因子权重 */}
          {strategy.factor_weights && Object.keys(strategy.factor_weights).length > 0 && (
            <GlassPanel>
              <Typography
                variant="h6"
                sx={{
                  mb: 3,
                  fontWeight: 600,
                  fontSize: '1.125rem',
                  color: '#e2e8f0',
                }}
              >
                因子权重配置
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {Object.entries(strategy.factor_weights).map(([factorId, weight]) => {
                  const totalWeight = Object.values(strategy.factor_weights!).reduce((a, b) => a + b, 0);
                  const percentage = totalWeight > 0 ? (weight / totalWeight) * 100 : 0;
                  const factorName = strategy.factors?.find(f => f.id === parseInt(factorId))?.factor_name || `因子 ${factorId}`;

                  return (
                    <Box
                      key={factorId}
                      sx={{
                        p: 2.5,
                        borderRadius: '12px',
                        background: 'rgba(15, 23, 42, 0.6)',
                        border: '1px solid rgba(148, 163, 184, 0.06)',
                        transition: 'all 0.2s',
                        '&:hover': {
                          borderColor: 'rgba(34, 211, 238, 0.2)',
                          background: 'rgba(15, 23, 42, 0.8)',
                        },
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                        <Typography
                          sx={{
                            fontSize: '0.9375rem',
                            fontWeight: 600,
                            color: '#e2e8f0',
                          }}
                        >
                          {factorName}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                          <Typography
                            sx={{
                              fontSize: '0.875rem',
                              color: '#64748b',
                            }}
                          >
                            权重: <span style={{ color: '#22d3ee', fontWeight: 600 }}>{weight.toFixed(4)}</span>
                          </Typography>
                          <Typography
                            sx={{
                              fontSize: '0.875rem',
                              color: '#64748b',
                            }}
                          >
                            占比: <span style={{ color: '#8b5cf6', fontWeight: 600 }}>{percentage.toFixed(2)}%</span>
                          </Typography>
                        </Box>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={percentage}
                        sx={{
                          height: 6,
                          borderRadius: '3px',
                          backgroundColor: 'rgba(148, 163, 184, 0.1)',
                          '& .MuiLinearProgress-bar': {
                            background: 'linear-gradient(90deg, #22d3ee 0%, #8b5cf6 100%)',
                            borderRadius: '3px',
                          },
                        }}
                      />
                    </Box>
                  );
                })}
              </Box>
            </GlassPanel>
          )}

          {/* 配置参数 */}
          {strategy.model_config && Object.keys(strategy.model_config).length > 0 && (
            <GlassPanel>
              <Typography
                variant="h6"
                sx={{
                  mb: 3,
                  fontWeight: 600,
                  fontSize: '1.125rem',
                  color: '#e2e8f0',
                }}
              >
                配置参数
              </Typography>
              <Box
                component="pre"
                sx={{
                  p: 3,
                  bgcolor: 'rgba(0, 0, 0, 0.4)',
                  borderRadius: '12px',
                  border: '1px solid rgba(148, 163, 184, 0.06)',
                  overflow: 'auto',
                  fontSize: '0.8125rem',
                  fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                  color: '#94a3b8',
                  lineHeight: 1.6,
                }}
              >
                {JSON.stringify(strategy.model_config, null, 2)}
              </Box>
            </GlassPanel>
          )}
        </Box>
      </motion.div>
    </Box>
  );
}
