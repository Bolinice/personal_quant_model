import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  TextField,
  Alert,
  CircularProgress,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Slider,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Save as SaveIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  AutoFixHigh as AutoFixHighIcon,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { strategyApi } from '../../api/strategies';
import { factorApi } from '../../api/factors';
import type { StrategyCreate, StrategyUpdate } from '../../api/types/strategies';
import type { Factor } from '../../api/types/factors';
import GlassPanel from '../../components/ui/GlassPanel';
import PageHeader from '../../components/ui/PageHeader';

interface FactorWeight {
  factor_id: number;
  factor_name: string;
  weight: number;
}

export default function StrategyForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableFactors, setAvailableFactors] = useState<Factor[]>([]);
  const [factorWeights, setFactorWeights] = useState<FactorWeight[]>([]);

  const [formData, setFormData] = useState({
    model_name: '',
    model_type: 'scoring',
    description: '',
  });

  useEffect(() => {
    loadFactors();
    if (isEdit && id) {
      loadStrategy(parseInt(id));
    } else {
      setLoading(false);
    }
  }, [id, isEdit]);

  const loadFactors = async () => {
    try {
      const response = await factorApi.getFactors({ page: 1, page_size: 100 });
      setAvailableFactors(response.items || []);
    } catch (err: any) {
      console.error('加载因子列表失败:', err);
    }
  };

  const loadStrategy = async (strategyId: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await strategyApi.get(strategyId);

      setFormData({
        model_name: data.model_name,
        model_type: data.model_type,
        description: data.description || '',
      });

      // 转换因子权重为表单格式
      if (data.factor_weights && typeof data.factor_weights === 'object') {
        const weights: FactorWeight[] = [];
        for (const [factorId, weight] of Object.entries(data.factor_weights)) {
          const factor = availableFactors.find(f => f.id === parseInt(factorId));
          weights.push({
            factor_id: parseInt(factorId),
            factor_name: factor?.factor_name || `因子 ${factorId}`,
            weight: Number(weight),
          });
        }
        setFactorWeights(weights);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载策略失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.model_name.trim()) {
      setError('请输入策略名称');
      return;
    }

    if (factorWeights.length === 0) {
      setError('请至少添加一个因子');
      return;
    }

    // 验证权重总和
    const totalWeight = factorWeights.reduce((sum, fw) => sum + fw.weight, 0);
    if (Math.abs(totalWeight - 1.0) > 0.01) {
      setError(`因子权重总和应为 1.0，当前为 ${totalWeight.toFixed(2)}`);
      return;
    }

    try {
      setSaving(true);
      setError(null);

      // 构建因子权重字典
      const factor_weights: Record<string, number> = {};
      const factor_ids: number[] = [];

      factorWeights.forEach(fw => {
        factor_weights[fw.factor_id.toString()] = fw.weight;
        factor_ids.push(fw.factor_id);
      });

      if (isEdit && id) {
        const updateData: StrategyUpdate = {
          model_name: formData.model_name,
          description: formData.description,
          factor_ids,
          factor_weights,
        };
        await strategyApi.update(parseInt(id), updateData);
        navigate(`/app/strategies/${id}`);
      } else {
        const createData: StrategyCreate = {
          model_name: formData.model_name,
          model_type: formData.model_type,
          description: formData.description,
          factor_ids,
          factor_weights,
          config: {},
        };
        const result = await strategyApi.create(createData);
        navigate(`/app/strategies/${result.id}`);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || `${isEdit ? '更新' : '创建'}策略失败`);
    } finally {
      setSaving(false);
    }
  };

  const handleAddFactor = () => {
    if (availableFactors.length === 0) return;

    // 找到第一个未添加的因子
    const usedIds = new Set(factorWeights.map(fw => fw.factor_id));
    const availableFactor = availableFactors.find(f => !usedIds.has(f.id));

    if (availableFactor) {
      setFactorWeights([
        ...factorWeights,
        {
          factor_id: availableFactor.id,
          factor_name: availableFactor.factor_name,
          weight: 0.1,
        },
      ]);
    }
  };

  const handleRemoveFactor = (index: number) => {
    setFactorWeights(factorWeights.filter((_, i) => i !== index));
  };

  const handleFactorChange = (index: number, factorId: number) => {
    const factor = availableFactors.find(f => f.id === factorId);
    if (factor) {
      const newWeights = [...factorWeights];
      newWeights[index] = {
        ...newWeights[index],
        factor_id: factorId,
        factor_name: factor.factor_name,
      };
      setFactorWeights(newWeights);
    }
  };

  const handleWeightChange = (index: number, weight: number) => {
    const newWeights = [...factorWeights];
    newWeights[index].weight = weight;
    setFactorWeights(newWeights);
  };

  const normalizeWeights = () => {
    const total = factorWeights.reduce((sum, fw) => sum + fw.weight, 0);
    if (total > 0) {
      setFactorWeights(
        factorWeights.map(fw => ({
          ...fw,
          weight: fw.weight / total,
        }))
      );
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress sx={{ color: '#22d3ee' }} />
      </Box>
    );
  }

  const totalWeight = factorWeights.reduce((sum, fw) => sum + fw.weight, 0);
  const usedFactorIds = new Set(factorWeights.map(fw => fw.factor_id));
  const availableForSelection = availableFactors.filter(f => !usedFactorIds.has(f.id));
  const isWeightValid = Math.abs(totalWeight - 1.0) <= 0.01;

  return (
    <Box>
      <PageHeader
        title={isEdit ? '编辑策略' : '新建策略'}
        subtitle={isEdit ? '修改策略配置和因子权重' : '创建新的多因子策略'}
        breadcrumbs={[
          { label: '首页', path: '/' },
          { label: '策略管理', path: '/app/strategies' },
          { label: isEdit ? '编辑策略' : '新建策略' },
        ]}
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
        <form onSubmit={handleSubmit}>
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
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' },
                    gap: 2.5,
                  }}
                >
                  <TextField
                    fullWidth
                    label="策略名称"
                    value={formData.model_name}
                    onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                    required
                    placeholder="例如：多因子选股策略 V1"
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
                  <FormControl fullWidth>
                    <InputLabel>策略类型</InputLabel>
                    <Select
                      value={formData.model_type}
                      label="策略类型"
                      onChange={(e) => setFormData({ ...formData, model_type: e.target.value })}
                      disabled={isEdit}
                      sx={{
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
                      }}
                    >
                      <MenuItem value="scoring">打分法</MenuItem>
                      <MenuItem value="classification">分类模型</MenuItem>
                      <MenuItem value="regression">回归模型</MenuItem>
                    </Select>
                  </FormControl>
                </Box>
                <TextField
                  fullWidth
                  label="策略描述"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  multiline
                  rows={3}
                  placeholder="简要描述策略的目标、方法和特点"
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
              </Box>
            </GlassPanel>

            {/* 因子权重配置 */}
            <GlassPanel>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                <Box>
                  <Typography
                    variant="h6"
                    sx={{
                      fontWeight: 600,
                      fontSize: '1.125rem',
                      color: '#e2e8f0',
                      mb: 0.5,
                    }}
                  >
                    因子权重配置
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                    <Typography
                      sx={{
                        fontSize: '0.8125rem',
                        color: '#64748b',
                      }}
                    >
                      权重总和:
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: '0.9375rem',
                        fontWeight: 700,
                        color: isWeightValid ? '#10b981' : '#ef4444',
                      }}
                    >
                      {totalWeight.toFixed(3)}
                    </Typography>
                    {!isWeightValid && (
                      <Typography
                        sx={{
                          fontSize: '0.75rem',
                          color: '#ef4444',
                          ml: 1,
                        }}
                      >
                        ⚠️ 应为 1.0
                      </Typography>
                    )}
                  </Box>
                </Box>
                <Box sx={{ display: 'flex', gap: 1.5 }}>
                  <Tooltip title="自动归一化权重">
                    <Button
                      size="small"
                      onClick={normalizeWeights}
                      disabled={factorWeights.length === 0}
                      startIcon={<AutoFixHighIcon />}
                      sx={{
                        color: '#8b5cf6',
                        borderColor: 'rgba(139, 92, 246, 0.3)',
                        fontWeight: 600,
                        textTransform: 'none',
                        '&:hover': {
                          borderColor: 'rgba(139, 92, 246, 0.5)',
                          backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        },
                      }}
                    >
                      归一化
                    </Button>
                  </Tooltip>
                  <Button
                    variant="outlined"
                    startIcon={<AddIcon />}
                    onClick={handleAddFactor}
                    disabled={availableForSelection.length === 0}
                    sx={{
                      borderColor: 'rgba(34, 211, 238, 0.3)',
                      color: '#22d3ee',
                      fontWeight: 600,
                      textTransform: 'none',
                      '&:hover': {
                        borderColor: 'rgba(34, 211, 238, 0.5)',
                        backgroundColor: 'rgba(34, 211, 238, 0.1)',
                      },
                    }}
                  >
                    添加因子
                  </Button>
                </Box>
              </Box>

              {factorWeights.length === 0 ? (
                <Box
                  sx={{
                    textAlign: 'center',
                    py: 8,
                    px: 3,
                    borderRadius: '12px',
                    background: 'rgba(15, 23, 42, 0.4)',
                    border: '1px solid rgba(148, 163, 184, 0.06)',
                  }}
                >
                  <AddIcon sx={{ fontSize: 48, color: '#64748b', mb: 2 }} />
                  <Typography sx={{ color: '#94a3b8', fontSize: '0.9375rem', mb: 0.5 }}>
                    暂无因子配置
                  </Typography>
                  <Typography sx={{ color: '#64748b', fontSize: '0.8125rem' }}>
                    点击"添加因子"按钮开始配置策略因子
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {factorWeights.map((fw, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: index * 0.05 }}
                    >
                      <Box
                        sx={{
                          p: 3,
                          borderRadius: '12px',
                          background: 'rgba(15, 23, 42, 0.6)',
                          border: '1px solid rgba(148, 163, 184, 0.08)',
                          transition: 'all 0.2s',
                          '&:hover': {
                            borderColor: 'rgba(34, 211, 238, 0.2)',
                            background: 'rgba(15, 23, 42, 0.8)',
                          },
                        }}
                      >
                        <Box
                          sx={{
                            display: 'grid',
                            gridTemplateColumns: { xs: '1fr', md: '2fr 3fr auto' },
                            gap: 3,
                            alignItems: 'center',
                          }}
                        >
                          {/* 因子选择 */}
                          <FormControl fullWidth size="small">
                            <InputLabel>选择因子</InputLabel>
                            <Select
                              value={fw.factor_id}
                              label="选择因子"
                              onChange={(e) => handleFactorChange(index, Number(e.target.value))}
                              sx={{
                                backgroundColor: 'rgba(0, 0, 0, 0.3)',
                                '& fieldset': {
                                  borderColor: 'rgba(148, 163, 184, 0.1)',
                                },
                              }}
                            >
                              <MenuItem value={fw.factor_id}>{fw.factor_name}</MenuItem>
                              {availableForSelection.map((factor) => (
                                <MenuItem key={factor.id} value={factor.id}>
                                  {factor.factor_name}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>

                          {/* 权重滑块 */}
                          <Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                              <Typography
                                sx={{
                                  fontSize: '0.75rem',
                                  color: '#64748b',
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.05em',
                                }}
                              >
                                权重
                              </Typography>
                              <Typography
                                sx={{
                                  fontSize: '0.875rem',
                                  fontWeight: 700,
                                  color: '#22d3ee',
                                }}
                              >
                                {fw.weight.toFixed(3)}
                              </Typography>
                            </Box>
                            <Slider
                              value={fw.weight}
                              onChange={(_, value) => handleWeightChange(index, value as number)}
                              min={0}
                              max={1}
                              step={0.01}
                              valueLabelDisplay="auto"
                              valueLabelFormat={(value) => value.toFixed(2)}
                              sx={{
                                color: '#22d3ee',
                                '& .MuiSlider-thumb': {
                                  width: 16,
                                  height: 16,
                                  '&:hover, &.Mui-focusVisible': {
                                    boxShadow: '0 0 0 8px rgba(34, 211, 238, 0.16)',
                                  },
                                },
                                '& .MuiSlider-track': {
                                  background: 'linear-gradient(90deg, #22d3ee 0%, #8b5cf6 100%)',
                                },
                                '& .MuiSlider-rail': {
                                  backgroundColor: 'rgba(148, 163, 184, 0.2)',
                                },
                              }}
                            />
                          </Box>

                          {/* 删除按钮 */}
                          <Tooltip title="删除因子">
                            <IconButton
                              onClick={() => handleRemoveFactor(index)}
                              size="small"
                              sx={{
                                color: '#94a3b8',
                                '&:hover': {
                                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                  color: '#ef4444',
                                },
                              }}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </Box>
                    </motion.div>
                  ))}
                </Box>
              )}
            </GlassPanel>

            {/* 提交按钮 */}
            <Box
              sx={{
                display: 'flex',
                gap: 2,
                justifyContent: 'flex-end',
                pt: 2,
              }}
            >
              <Button
                variant="outlined"
                onClick={() => navigate('/app/strategies')}
                sx={{
                  borderColor: 'rgba(148, 163, 184, 0.3)',
                  color: '#94a3b8',
                  fontWeight: 600,
                  px: 4,
                  py: 1.25,
                  borderRadius: '10px',
                  textTransform: 'none',
                  '&:hover': {
                    borderColor: 'rgba(148, 163, 184, 0.5)',
                    backgroundColor: 'rgba(148, 163, 184, 0.05)',
                  },
                }}
              >
                取消
              </Button>
              <Button
                type="submit"
                variant="contained"
                startIcon={<SaveIcon />}
                disabled={saving || factorWeights.length === 0 || !isWeightValid}
                sx={{
                  background: 'linear-gradient(135deg, #22d3ee 0%, #3b82f6 100%)',
                  color: '#0f172a',
                  fontWeight: 600,
                  px: 4,
                  py: 1.25,
                  borderRadius: '10px',
                  textTransform: 'none',
                  boxShadow: '0 4px 12px rgba(34, 211, 238, 0.3)',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #06b6d4 0%, #2563eb 100%)',
                    boxShadow: '0 6px 16px rgba(34, 211, 238, 0.4)',
                  },
                  '&:disabled': {
                    background: 'rgba(148, 163, 184, 0.2)',
                    color: 'rgba(148, 163, 184, 0.5)',
                  },
                }}
              >
                {saving ? '保存中...' : '保存策略'}
              </Button>
            </Box>
          </Box>
        </form>
      </motion.div>
    </Box>
  );
}
