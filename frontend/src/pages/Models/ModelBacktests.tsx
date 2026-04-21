import { useState, useEffect } from 'react';
import {
  Box, Grid, Typography, Select, MenuItem, FormControl, InputLabel, TextField,
} from '@mui/material';
import { motion } from 'framer-motion';
import { PageHeader, GlassPanel, MetricCard, NeonChip } from '@/components/ui';
import { modelApi, backtestApi } from '@/api';
import type { Model, ModelPerformance } from '@/api';
import { useLang } from '@/i18n';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AssessmentIcon from '@mui/icons-material/Assessment';
import BarChartIcon from '@mui/icons-material/BarChart';
import SpeedIcon from '@mui/icons-material/Speed';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import LockIcon from '@mui/icons-material/Lock';
import FilterListIcon from '@mui/icons-material/FilterList';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';

const fmt = (v: number | null | undefined, pct = false) => {
  if (v == null) return '-';
  return pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(4);
};

function computeMetrics(perf: ModelPerformance[]) {
  if (perf.length === 0) {
    return {
      annualReturn: null as number | null,
      maxDrawdown: null as number | null,
      sharpe: null as number | null,
      volatility: null as number | null,
      winRate: null as number | null,
      turnover: null as number | null,
    };
  }

  const dailyReturns = perf
    .map((p) => p.daily_return)
    .filter((v): v is number => v != null);

  const latest = perf[0];
  const annualReturn = latest.cumulative_return ?? null;

  const maxDrawdown =
    perf.reduce(
      (worst, p) => (p.max_drawdown != null ? Math.min(worst, p.max_drawdown) : worst),
      0
    ) || null;

  const sharpe = latest.sharpe_ratio ?? null;

  let volatility: number | null = null;
  if (dailyReturns.length > 1) {
    const mean = dailyReturns.reduce((s, v) => s + v, 0) / dailyReturns.length;
    const variance =
      dailyReturns.reduce((s, v) => s + (v - mean) ** 2, 0) /
      (dailyReturns.length - 1);
    volatility = Math.sqrt(variance) * Math.sqrt(252);
  }

  const positiveCount = dailyReturns.filter((v) => v > 0).length;
  const winRate = dailyReturns.length > 0 ? positiveCount / dailyReturns.length : null;

  const turnoverValues = perf
    .map((p) => p.turnover)
    .filter((v): v is number => v != null);
  const turnover =
    turnoverValues.length > 0
      ? turnoverValues.reduce((s, v) => s + v, 0) / turnoverValues.length
      : null;

  return { annualReturn, maxDrawdown, sharpe, volatility, winRate, turnover };
}

export default function ModelBacktests() {
  const { t } = useLang();

  const [models, setModels] = useState<Model[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<number | ''>('');
  const [selectedVersion, setSelectedVersion] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [performance, setPerformance] = useState<ModelPerformance[]>([]);
  const [loading, setLoading] = useState(true);
  const [perfLoading, setPerfLoading] = useState(false);

  // Available versions derived from models sharing the same model_code
  const selectedModel = models.find((m) => m.id === selectedModelId) || null;
  const availableVersions = selectedModel
    ? models
        .filter((m) => m.model_code === selectedModel.model_code)
        .map((m) => m.version)
    : [];

  // Fetch models on mount
  useEffect(() => {
    modelApi
      .list({ limit: 200 })
      .then((res) => setModels(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Fetch performance when model changes
  useEffect(() => {
    if (!selectedModelId) {
      setPerformance([]);
      return;
    }
    setPerfLoading(true);
    modelApi
      .getPerformance(selectedModelId as number, { limit: 200 })
      .then((res) => setPerformance(res.data))
      .catch(() => setPerformance([]))
      .finally(() => setPerfLoading(false));
  }, [selectedModelId]);

  // When version changes, switch to the corresponding model id
  const handleVersionChange = (version: string) => {
    setSelectedVersion(version);
    if (!selectedModel) return;
    const match = models.find(
      (m) => m.model_code === selectedModel.model_code && m.version === version
    );
    if (match) setSelectedModelId(match.id);
  };

  const metrics = computeMetrics(performance);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <Typography sx={{ color: '#94a3b8' }}>Loading...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title={t.models.backtests} />

      {/* ── Model selector bar ─────────────────────────────────── */}
      <GlassPanel animate={false} sx={{ mb: 3, p: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <FilterListIcon sx={{ color: '#64748b', mr: 0.5 }} />

        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel sx={{ color: '#94a3b8', fontSize: '0.875rem' }}>
            {t.models.selectModel}
          </InputLabel>
          <Select
            value={selectedModelId}
            label={t.models.selectModel}
            onChange={(e) => {
              const id = e.target.value as number | '';
              setSelectedModelId(id);
              const m = models.find((x) => x.id === id);
              if (m) setSelectedVersion(m.version);
            }}
            sx={{ fontSize: '0.875rem', color: '#e2e8f0' }}
          >
            <MenuItem value="">
              <em>{t.models.selectModel}</em>
            </MenuItem>
            {models.map((m) => (
              <MenuItem key={m.id} value={m.id}>
                {m.model_name} ({m.model_code})
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel sx={{ color: '#94a3b8', fontSize: '0.875rem' }}>
            Version
          </InputLabel>
          <Select
            value={selectedVersion}
            label="Version"
            onChange={(e) => handleVersionChange(e.target.value)}
            sx={{ fontSize: '0.875rem', color: '#e2e8f0' }}
            disabled={!selectedModelId}
          >
            {availableVersions.map((v) => (
              <MenuItem key={v} value={v}>
                v{v}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <CompareArrowsIcon sx={{ color: '#475569', fontSize: 18, mx: 0.5 }} />

        <TextField
          size="small"
          type="date"
          label={t.models.selectPeriod}
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          InputLabelProps={{ shrink: true, sx: { color: '#94a3b8', fontSize: '0.875rem' } }}
          sx={{ minWidth: 160, '& .MuiOutlinedInput-root': { fontSize: '0.875rem', color: '#e2e8f0' } }}
        />
        <Typography sx={{ color: '#475569', alignSelf: 'center' }}>-</Typography>
        <TextField
          size="small"
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          InputLabelProps={{ shrink: true, sx: { color: '#94a3b8', fontSize: '0.875rem' } }}
          sx={{ minWidth: 160, '& .MuiOutlinedInput-root': { fontSize: '0.875rem', color: '#e2e8f0' } }}
        />

        {selectedModel && (
          <NeonChip label={`v${selectedModel.version}`} size="small" neonColor="indigo" />
        )}
      </GlassPanel>

      {/* ── Chart placeholders ─────────────────────────────────── */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <GlassPanel animate={false}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#e2e8f0', mb: 2 }}>
              收益曲线
            </Typography>
            <Box
              sx={{
                height: 300,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background:
                  'linear-gradient(180deg, rgba(34, 211, 238, 0.03) 0%, rgba(139, 92, 246, 0.03) 100%)',
                borderRadius: 2,
                border: '1px dashed rgba(148, 163, 184, 0.15)',
              }}
            >
              {perfLoading ? (
                <Typography sx={{ color: '#64748b' }}>Loading...</Typography>
              ) : performance.length === 0 ? (
                <Typography sx={{ color: '#475569' }}>Select a model to view</Typography>
              ) : (
                <Typography sx={{ color: '#64748b' }}>图表区域</Typography>
              )}
            </Box>
          </GlassPanel>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <GlassPanel animate={false}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#e2e8f0', mb: 2 }}>
              回撤曲线
            </Typography>
            <Box
              sx={{
                height: 300,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background:
                  'linear-gradient(180deg, rgba(244, 63, 94, 0.03) 0%, rgba(245, 158, 11, 0.03) 100%)',
                borderRadius: 2,
                border: '1px dashed rgba(148, 163, 184, 0.15)',
              }}
            >
              {perfLoading ? (
                <Typography sx={{ color: '#64748b' }}>Loading...</Typography>
              ) : performance.length === 0 ? (
                <Typography sx={{ color: '#475569' }}>Select a model to view</Typography>
              ) : (
                <Typography sx={{ color: '#64748b' }}>图表区域</Typography>
              )}
            </Box>
          </GlassPanel>
        </Grid>
      </Grid>

      {/* ── Metric cards ───────────────────────────────────────── */}
      {performance.length > 0 && (
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <MetricCard
              label={t.models.annualReturn}
              value={fmt(metrics.annualReturn, true)}
              color="#22d3ee"
              icon={<TrendingUpIcon />}
              delay={0}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <MetricCard
              label={t.models.maxDrawdown}
              value={fmt(metrics.maxDrawdown, true)}
              color="#f43f5e"
              icon={<AssessmentIcon />}
              delay={0.05}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <MetricCard
              label={t.models.sharpe}
              value={fmt(metrics.sharpe)}
              color="#8b5cf6"
              icon={<ShowChartIcon />}
              delay={0.1}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <MetricCard
              label={t.models.volatility}
              value={fmt(metrics.volatility, true)}
              color="#f59e0b"
              icon={<SpeedIcon />}
              delay={0.15}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <MetricCard
              label={t.models.winRate}
              value={metrics.winRate != null ? `${(metrics.winRate * 100).toFixed(1)}%` : '-'}
              color="#10b981"
              icon={<BarChartIcon />}
              delay={0.2}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <MetricCard
              label={t.models.turnover}
              value={fmt(metrics.turnover, true)}
              color="#6366f1"
              icon={<SwapHorizIcon />}
              delay={0.25}
            />
          </Grid>
        </Grid>
      )}

      {/* ── Depth analysis (locked) ────────────────────────────── */}
      <GlassPanel animate={false} sx={{ position: 'relative' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#e2e8f0', mb: 2 }}>
          {t.models.depthAnalysis}
        </Typography>

        <Grid container spacing={2.5}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Box
              sx={{
                height: 200,
                borderRadius: 2,
                background: 'rgba(15, 23, 42, 0.4)',
                border: '1px solid rgba(148, 163, 184, 0.08)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1,
              }}
            >
              <BarChartIcon sx={{ fontSize: 32, color: '#475569' }} />
              <Typography sx={{ color: '#64748b', fontSize: '0.875rem' }}>
                {t.models.industryExposure}
              </Typography>
            </Box>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Box
              sx={{
                height: 200,
                borderRadius: 2,
                background: 'rgba(15, 23, 42, 0.4)',
                border: '1px solid rgba(148, 163, 184, 0.08)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1,
              }}
            >
              <ShowChartIcon sx={{ fontSize: 32, color: '#475569' }} />
              <Typography sx={{ color: '#64748b', fontSize: '0.875rem' }}>
                {t.models.styleExposure}
              </Typography>
            </Box>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Box
              sx={{
                height: 200,
                borderRadius: 2,
                background: 'rgba(15, 23, 42, 0.4)',
                border: '1px solid rgba(148, 163, 184, 0.08)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1,
              }}
            >
              <AssessmentIcon sx={{ fontSize: 32, color: '#475569' }} />
              <Typography sx={{ color: '#64748b', fontSize: '0.875rem' }}>
                {t.models.factorExposure}
              </Typography>
            </Box>
          </Grid>
        </Grid>

        {/* Lock overlay */}
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            borderRadius: 3,
            background: 'rgba(3, 7, 18, 0.65)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 1.5,
            zIndex: 10,
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            <LockIcon sx={{ fontSize: 40, color: '#64748b' }} />
          </motion.div>
          <Typography sx={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.95rem' }}>
            {t.models.locked}
          </Typography>
          <Box
            sx={{
              px: 2.5,
              py: 0.75,
              borderRadius: 2,
              background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
              color: '#030712',
              fontWeight: 700,
              fontSize: '0.875rem',
              cursor: 'pointer',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
              '&:hover': {
                transform: 'translateY(-1px)',
                boxShadow: '0 0 20px rgba(34, 211, 238, 0.3)',
              },
            }}
          >
            {t.models.unlockUpgrade}
          </Box>
        </Box>
      </GlassPanel>
    </Box>
  );
}
