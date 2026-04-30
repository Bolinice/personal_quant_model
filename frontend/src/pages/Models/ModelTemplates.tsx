import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Typography,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import { motion } from 'framer-motion';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import SpeedIcon from '@mui/icons-material/Speed';
import ShieldIcon from '@mui/icons-material/Shield';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { PageHeader, GlassPanel, NeonChip } from '@/components/ui';
import { useLang } from '@/i18n';

/* ── Pool color / neon mapping ── */
const POOL_COLORS: Record<string, string> = {
  HS300: '#22d3ee',
  ZZ500: '#8b5cf6',
  ZZ1000: '#10b981',
  ALL_A: '#f59e0b',
};

const POOL_NEON: Record<string, 'cyan' | 'purple' | 'green' | 'amber'> = {
  HS300: 'cyan',
  ZZ500: 'purple',
  ZZ1000: 'green',
  ALL_A: 'amber',
};

const RISK_CONFIG: Record<
  string,
  { label: string; color: string; neon: 'green' | 'amber' | 'red'; icon: React.ReactNode }
> = {
  low: {
    label: '低风险',
    color: '#10b981',
    neon: 'green',
    icon: <ShieldIcon sx={{ fontSize: 16 }} />,
  },
  medium: {
    label: '中风险',
    color: '#f59e0b',
    neon: 'amber',
    icon: <SpeedIcon sx={{ fontSize: 16 }} />,
  },
  high: {
    label: '高风险',
    color: '#f43f5e',
    neon: 'red',
    icon: <RocketLaunchIcon sx={{ fontSize: 16 }} />,
  },
};

const FREQ_LABELS: Record<string, string> = {
  daily: '日频',
  weekly: '周频',
  monthly: '月频',
};

const TAG_NEON: Record<string, 'green' | 'cyan' | 'purple'> = {
  recommend: 'green',
  beginner: 'cyan',
  pro: 'purple',
};

/* ── Hardcoded templates (MVP) ── */
const TEMPLATES = [
  {
    id: 1,
    name: '沪深300增强',
    description: '基于多因子模型的沪深300指数增强策略，适合稳健型投资者',
    pools: ['HS300'],
    frequencies: ['daily', 'weekly'],
    riskLevel: 'low',
    tags: ['recommend', 'beginner'],
  },
  {
    id: 2,
    name: '中证500增强',
    description: '中证500指数增强策略，平衡收益与风险',
    pools: ['ZZ500'],
    frequencies: ['daily', 'weekly'],
    riskLevel: 'medium',
    tags: ['recommend'],
  },
  {
    id: 3,
    name: '全A股量化选股',
    description: '全市场量化选股策略，追求超额收益',
    pools: ['ALL_A'],
    frequencies: ['daily'],
    riskLevel: 'high',
    tags: ['pro'],
  },
  {
    id: 4,
    name: '中证1000增强',
    description: '中证1000小盘股增强策略，高弹性高收益',
    pools: ['ZZ1000'],
    frequencies: ['daily', 'weekly', 'monthly'],
    riskLevel: 'high',
    tags: ['pro'],
  },
  {
    id: 5,
    name: '低波动策略',
    description: '最小化组合波动率，适合保守型投资者',
    pools: ['HS300', 'ZZ500'],
    frequencies: ['monthly'],
    riskLevel: 'low',
    tags: ['beginner'],
  },
  {
    id: 6,
    name: '多频率组合',
    description: '结合日频和周频信号的综合策略',
    pools: ['HS300', 'ZZ500', 'ZZ1000'],
    frequencies: ['daily', 'weekly'],
    riskLevel: 'medium',
    tags: ['recommend'],
  },
];

/* ── Filter options ── */
const POOL_OPTIONS = [
  { value: '', label: '全部股票池' },
  { value: 'HS300', label: '沪深300' },
  { value: 'ZZ500', label: '中证500' },
  { value: 'ZZ1000', label: '中证1000' },
  { value: 'ALL_A', label: '全A股' },
];

const FREQ_OPTIONS = [
  { value: '', label: '全部频率' },
  { value: 'daily', label: '日频' },
  { value: 'weekly', label: '周频' },
  { value: 'monthly', label: '月频' },
];

const RISK_OPTIONS = [
  { value: '', label: '全部风险' },
  { value: 'low', label: '低风险' },
  { value: 'medium', label: '中风险' },
  { value: 'high', label: '高风险' },
];

/* ── Dark-themed Select styling ── */
const selectSx = {
  minWidth: 140,
  '& .MuiOutlinedInput-root': {
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    backdropFilter: 'blur(8px)',
    borderRadius: 2,
    color: '#e2e8f0',
    fontSize: '0.875rem',
    '& fieldset': {
      borderColor: 'rgba(148, 163, 184, 0.2)',
    },
    '&:hover fieldset': {
      borderColor: 'rgba(148, 163, 184, 0.35)',
    },
    '&.Mui-focused fieldset': {
      borderColor: '#22d3ee',
    },
  },
  '& .MuiInputLabel-root': {
    color: '#94a3b8',
    fontSize: '0.875rem',
    '&.Mui-focused': {
      color: '#22d3ee',
    },
  },
  '& .MuiSvgIcon-root': {
    color: '#94a3b8',
  },
};

/* ── Component ── */
export default function ModelTemplates() {
  const navigate = useNavigate();
  const { t } = useLang();

  const [poolFilter, setPoolFilter] = useState('');
  const [freqFilter, setFreqFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');

  /* Filter logic */
  const filtered = TEMPLATES.filter((tpl) => {
    if (poolFilter && !tpl.pools.includes(poolFilter)) return false;
    if (freqFilter && !tpl.frequencies.includes(freqFilter)) return false;
    if (riskFilter && tpl.riskLevel !== riskFilter) return false;
    return true;
  });

  /* Tag i18n mapping */
  const tagLabel = (tag: string): string => {
    switch (tag) {
      case 'recommend':
        return t.models.templateRecommend;
      case 'beginner':
        return t.models.templateBeginner;
      case 'pro':
        return t.models.templatePro;
      default:
        return tag;
    }
  };

  return (
    <Box>
      <PageHeader title={t.models.templates} />

      {/* ── Filter toolbar ── */}
      <GlassPanel
        animate={false}
        sx={{ mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}
      >
        <FormControl size="small" sx={selectSx}>
          <InputLabel>{t.models.availablePools}</InputLabel>
          <Select
            value={poolFilter}
            label={t.models.availablePools}
            onChange={(e) => setPoolFilter(e.target.value)}
          >
            {POOL_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value} sx={{ color: '#e2e8f0' }}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={selectSx}>
          <InputLabel>{t.models.availableFreq}</InputLabel>
          <Select
            value={freqFilter}
            label={t.models.availableFreq}
            onChange={(e) => setFreqFilter(e.target.value)}
          >
            {FREQ_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value} sx={{ color: '#e2e8f0' }}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={selectSx}>
          <InputLabel>风险偏好</InputLabel>
          <Select
            value={riskFilter}
            label="风险偏好"
            onChange={(e) => setRiskFilter(e.target.value)}
          >
            {RISK_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value} sx={{ color: '#e2e8f0' }}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </GlassPanel>

      {/* ── Template cards ── */}
      <Grid container spacing={2.5}>
        {filtered.map((tpl, i) => {
          const risk = RISK_CONFIG[tpl.riskLevel];
          return (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={tpl.id}>
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
              >
                <GlassPanel
                  glow
                  glowColor={POOL_COLORS[tpl.pools[0]] || '#22d3ee'}
                  animate={false}
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1.5,
                    height: '100%',
                    transition: 'all 0.3s ease',
                    '&:hover': {
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  {/* Name */}
                  <Typography
                    sx={{
                      fontWeight: 700,
                      color: '#e2e8f0',
                      fontSize: '1.1rem',
                    }}
                  >
                    {tpl.name}
                  </Typography>

                  {/* Description */}
                  <Typography variant="body2" sx={{ color: '#64748b', lineHeight: 1.6 }}>
                    {tpl.description}
                  </Typography>

                  {/* Pool chips */}
                  <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                    {tpl.pools.map((pool) => (
                      <NeonChip
                        key={pool}
                        label={pool}
                        size="small"
                        neonColor={POOL_NEON[pool] || 'default'}
                      />
                    ))}
                  </Box>

                  {/* Frequency chips */}
                  <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                    {tpl.frequencies.map((freq) => (
                      <NeonChip
                        key={freq}
                        label={FREQ_LABELS[freq] || freq}
                        size="small"
                        neonColor="blue"
                      />
                    ))}
                  </Box>

                  {/* Risk level */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                    {risk.icon}
                    <NeonChip label={risk.label} size="small" neonColor={risk.neon} />
                  </Box>

                  {/* Tags + Use button */}
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      mt: 'auto',
                      pt: 1,
                    }}
                  >
                    <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                      {tpl.tags.map((tag) => (
                        <NeonChip
                          key={tag}
                          label={tagLabel(tag)}
                          size="small"
                          neonColor={TAG_NEON[tag] || 'default'}
                        />
                      ))}
                    </Box>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<TrendingUpIcon sx={{ fontSize: 16 }} />}
                      onClick={() => navigate('/app/models')}
                      sx={{
                        borderColor: `${POOL_COLORS[tpl.pools[0]] || '#22d3ee'}55`,
                        color: POOL_COLORS[tpl.pools[0]] || '#22d3ee',
                        fontSize: '0.8rem',
                        textTransform: 'none',
                        '&:hover': {
                          borderColor: POOL_COLORS[tpl.pools[0]] || '#22d3ee',
                          backgroundColor: `${POOL_COLORS[tpl.pools[0]] || '#22d3ee'}12`,
                        },
                      }}
                    >
                      {t.models.useTemplate}
                    </Button>
                  </Box>
                </GlassPanel>
              </motion.div>
            </Grid>
          );
        })}

        {filtered.length === 0 && (
          <Grid size={12}>
            <Typography sx={{ textAlign: 'center', color: '#64748b', py: 6 }}>
              没有匹配的模板
            </Typography>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
