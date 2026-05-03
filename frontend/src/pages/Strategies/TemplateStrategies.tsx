import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Typography,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  CardActions,
  Chip,
  Grid,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import TimelineIcon from '@mui/icons-material/Timeline';
import AssessmentIcon from '@mui/icons-material/Assessment';
import { motion } from 'framer-motion';
import PageHeader from '../../components/ui/PageHeader';
import { templateApi } from '../../api/templates';
import type { TemplateStrategy } from '../../api/types/templates';

export default function TemplateStrategies() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<TemplateStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await templateApi.list();
      setTemplates(data);
    } catch (err: any) {
      console.error('Failed to load templates:', err);
      setError(err.message || '加载模板策略失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUseTemplate = (template: TemplateStrategy) => {
    // Navigate to strategy creation with template pre-filled
    navigate('/app/strategies/new', { state: { template } });
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
        title="模板策略"
        subtitle="基于历史回测的预配置策略模板"
        breadcrumbs={[
          { label: '首页', path: '/' },
          { label: '模板策略' },
        ]}
      />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              md: 'repeat(2, 1fr)',
              lg: 'repeat(3, 1fr)',
            },
            gap: 3,
            mt: 3,
          }}
        >
          {templates.map((template, index) => (
            <motion.div
              key={template.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.1 }}
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
                  {/* 标题 */}
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                    <Typography
                      variant="h6"
                      sx={{
                        color: '#e2e8f0',
                        fontWeight: 600,
                        fontSize: '1.25rem',
                      }}
                    >
                      {template.model_name}
                    </Typography>
                    <Chip
                      label="模板"
                      size="small"
                      sx={{
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        color: '#a78bfa',
                        border: '1px solid rgba(139, 92, 246, 0.2)',
                        fontWeight: 600,
                      }}
                    />
                  </Box>

                  {/* 描述 */}
                  <Typography
                    sx={{
                      color: '#94a3b8',
                      fontSize: '0.875rem',
                      lineHeight: 1.6,
                      mb: 3,
                      minHeight: '2.8em',
                    }}
                  >
                    {template.description}
                  </Typography>

                  {/* 回测结果 */}
                  {template.backtest_result ? (
                    <>
                      <Box
                        sx={{
                          mb: 2,
                          pb: 2,
                          borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
                        }}
                      >
                        <Typography
                          sx={{
                            color: '#64748b',
                            fontSize: '0.75rem',
                            mb: 1,
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                          }}
                        >
                          历史回测结果
                        </Typography>
                        <Typography sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                          {template.backtest_result.start_date} 至 {template.backtest_result.end_date}
                        </Typography>
                      </Box>

                      {/* 关键指标网格 */}
                      <Grid container spacing={2}>
                        <Grid item xs={6}>
                          <Box
                            sx={{
                              p: 2,
                              borderRadius: '12px',
                              background: 'rgba(34, 211, 238, 0.05)',
                              border: '1px solid rgba(34, 211, 238, 0.1)',
                            }}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                              <TrendingUpIcon sx={{ fontSize: 14, color: '#22d3ee' }} />
                              <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                                年化收益
                              </Typography>
                            </Box>
                            <Typography
                              sx={{
                                fontSize: '1.25rem',
                                fontWeight: 700,
                                color: template.backtest_result.annual_return >= 0 ? '#10b981' : '#ef4444',
                              }}
                            >
                              {(template.backtest_result.annual_return * 100).toFixed(2)}%
                            </Typography>
                          </Box>
                        </Grid>

                        <Grid item xs={6}>
                          <Box
                            sx={{
                              p: 2,
                              borderRadius: '12px',
                              background: 'rgba(139, 92, 246, 0.05)',
                              border: '1px solid rgba(139, 92, 246, 0.1)',
                            }}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                              <ShowChartIcon sx={{ fontSize: 14, color: '#8b5cf6' }} />
                              <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                                夏普比率
                              </Typography>
                            </Box>
                            <Typography
                              sx={{
                                fontSize: '1.25rem',
                                fontWeight: 700,
                                color: '#e2e8f0',
                              }}
                            >
                              {template.backtest_result.sharpe.toFixed(2)}
                            </Typography>
                          </Box>
                        </Grid>

                        <Grid item xs={6}>
                          <Box
                            sx={{
                              p: 2,
                              borderRadius: '12px',
                              background: 'rgba(239, 68, 68, 0.05)',
                              border: '1px solid rgba(239, 68, 68, 0.1)',
                            }}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                              <TimelineIcon sx={{ fontSize: 14, color: '#ef4444' }} />
                              <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                                最大回撤
                              </Typography>
                            </Box>
                            <Typography
                              sx={{
                                fontSize: '1.25rem',
                                fontWeight: 700,
                                color: '#ef4444',
                              }}
                            >
                              {(template.backtest_result.max_drawdown * 100).toFixed(2)}%
                            </Typography>
                          </Box>
                        </Grid>

                        <Grid item xs={6}>
                          <Box
                            sx={{
                              p: 2,
                              borderRadius: '12px',
                              background: 'rgba(59, 130, 246, 0.05)',
                              border: '1px solid rgba(59, 130, 246, 0.1)',
                            }}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                              <AssessmentIcon sx={{ fontSize: 14, color: '#3b82f6' }} />
                              <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                                胜率
                              </Typography>
                            </Box>
                            <Typography
                              sx={{
                                fontSize: '1.25rem',
                                fontWeight: 700,
                                color: '#e2e8f0',
                              }}
                            >
                              {(template.backtest_result.win_rate * 100).toFixed(0)}%
                            </Typography>
                          </Box>
                        </Grid>
                      </Grid>

                      {/* 免责声明 */}
                      <Box
                        sx={{
                          mt: 2,
                          p: 1.5,
                          borderRadius: '8px',
                          background: 'rgba(251, 191, 36, 0.05)',
                          border: '1px solid rgba(251, 191, 36, 0.1)',
                        }}
                      >
                        <Typography
                          sx={{
                            color: '#fbbf24',
                            fontSize: '0.7rem',
                            lineHeight: 1.4,
                          }}
                        >
                          ⚠️ 历史回测结果，不代表未来表现
                        </Typography>
                      </Box>
                    </>
                  ) : (
                    <Alert
                      severity="info"
                      sx={{
                        background: 'rgba(59, 130, 246, 0.05)',
                        border: '1px solid rgba(59, 130, 246, 0.1)',
                        color: '#93c5fd',
                        fontSize: '0.875rem',
                      }}
                    >
                      暂无回测数据
                    </Alert>
                  )}
                </CardContent>

                {/* 操作按钮 */}
                <CardActions sx={{ p: 3, pt: 0 }}>
                  <Button
                    fullWidth
                    variant="contained"
                    onClick={() => handleUseTemplate(template)}
                    sx={{
                      background: 'linear-gradient(135deg, #22d3ee 0%, #3b82f6 100%)',
                      color: '#0f172a',
                      fontWeight: 600,
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
                    使用此模板
                  </Button>
                </CardActions>
              </Card>
            </motion.div>
          ))}
        </Box>
      </motion.div>
    </Box>
  );
}
