import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Menu,
  Snackbar,
  Alert,
} from '@mui/material';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import AddIcon from '@mui/icons-material/Add';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import AssessmentIcon from '@mui/icons-material/Assessment';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import { motion } from 'framer-motion';
import { modelApi, stockPoolApi } from '@/api';
import type { Model, StockPool } from '@/api';
import { PageHeader, GlassPanel, MetricCard, NeonChip, GlassTable } from '@/components/ui';
import { useLang } from '@/i18n';

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
const POOL_NAMES: Record<string, string> = {
  HS300: '沪深300',
  ZZ500: '中证500',
  ZZ1000: '中证1000',
  ALL_A: '全A股',
};
const FREQ_LABELS: Record<string, string> = {
  daily: '日频',
  weekly: '周频',
  monthly: '月频',
};

const fmt = (v: number | null | undefined, pct = false) => {
  if (v == null) return '-';
  return pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(4);
};

type ViewMode = 'card' | 'table';

export default function ModelList() {
  const navigate = useNavigate();
  const { t } = useLang();
  const [models, setModels] = useState<Model[]>([]);
  const [pools, setPools] = useState<StockPool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('card');
  const [search, setSearch] = useState('');
  const [poolFilter, setPoolFilter] = useState('all');
  const [freqFilter, setFreqFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [menuModel, setMenuModel] = useState<Model | null>(null);

  useEffect(() => {
    Promise.all([modelApi.list({ limit: 200 }), stockPoolApi.list({ limit: 200 })])
      .then(([modelsRes, poolsRes]) => {
        setModels(modelsRes.data);
        setPools(poolsRes.data.filter((p) => p.is_active));
      })
      .catch(() => setError('加载数据失败'))
      .finally(() => setLoading(false));
  }, []);

  // Infer pool/freq from model_code (e.g. "HS300_DAILY_V1")
  const inferPool = (code: string) => {
    const upper = code.toUpperCase();
    for (const key of Object.keys(POOL_NAMES)) {
      if (upper.includes(key)) return key;
    }
    return '';
  };
  const inferFreq = (code: string) => {
    const upper = code.toUpperCase();
    if (upper.includes('DAILY')) return 'daily';
    if (upper.includes('WEEKLY')) return 'weekly';
    if (upper.includes('MONTHLY')) return 'monthly';
    return '';
  };

  const filtered = models.filter((m) => {
    if (
      search &&
      !m.model_name.toLowerCase().includes(search.toLowerCase()) &&
      !m.model_code.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    if (poolFilter !== 'all' && inferPool(m.model_code) !== poolFilter) return false;
    if (freqFilter !== 'all' && inferFreq(m.model_code) !== freqFilter) return false;
    if (statusFilter !== 'all' && m.status !== statusFilter) return false;
    return true;
  });

  const handleMenuOpen = (e: React.MouseEvent<HTMLElement>, model: Model) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
    setMenuModel(model);
  };
  const handleMenuClose = () => {
    setMenuAnchor(null);
    setMenuModel(null);
  };

  if (loading) return <Typography>{t.models.myModels}</Typography>;

  return (
    <Box>
      <PageHeader
        title={t.models.myModels}
        actions={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={t.models.cardView}>
              <IconButton
                onClick={() => setViewMode('card')}
                sx={{ color: viewMode === 'card' ? '#22d3ee' : '#64748b' }}
              >
                <ViewModuleIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title={t.models.tableView}>
              <IconButton
                onClick={() => setViewMode('table')}
                sx={{ color: viewMode === 'table' ? '#22d3ee' : '#64748b' }}
              >
                <ViewListIcon />
              </IconButton>
            </Tooltip>
            <button
              onClick={() => navigate('/app/models/overview')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 16px',
                borderRadius: 8,
                background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
                color: '#030712',
                fontWeight: 600,
                fontSize: '0.875rem',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <AddIcon sx={{ fontSize: 18 }} />
              {t.models.newModel}
            </button>
          </Box>
        }
      />

      {/* Filter toolbar */}
      <GlassPanel
        animate={false}
        sx={{ mb: 3, p: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}
      >
        <TextField
          size="small"
          placeholder={t.models.searchModel}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 200, '& .MuiOutlinedInput-root': { fontSize: '0.875rem' } }}
        />
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel sx={{ color: '#94a3b8', fontSize: '0.875rem' }}>
            {t.models.availablePools}
          </InputLabel>
          <Select
            value={poolFilter}
            label={t.models.availablePools}
            onChange={(e) => setPoolFilter(e.target.value)}
            sx={{ fontSize: '0.875rem', color: '#e2e8f0' }}
          >
            <MenuItem value="all">全部</MenuItem>
            {pools.map((p) => (
              <MenuItem key={p.pool_code} value={p.pool_code}>
                {p.pool_name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel sx={{ color: '#94a3b8', fontSize: '0.875rem' }}>
            {t.models.availableFreq}
          </InputLabel>
          <Select
            value={freqFilter}
            label={t.models.availableFreq}
            onChange={(e) => setFreqFilter(e.target.value)}
            sx={{ fontSize: '0.875rem', color: '#e2e8f0' }}
          >
            <MenuItem value="all">全部</MenuItem>
            <MenuItem value="daily">日频</MenuItem>
            <MenuItem value="weekly">周频</MenuItem>
            <MenuItem value="monthly">月频</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel sx={{ color: '#94a3b8', fontSize: '0.875rem' }}>状态</InputLabel>
          <Select
            value={statusFilter}
            label="状态"
            onChange={(e) => setStatusFilter(e.target.value)}
            sx={{ fontSize: '0.875rem', color: '#e2e8f0' }}
          >
            <MenuItem value="all">全部</MenuItem>
            <MenuItem value="active">{t.models.running}</MenuItem>
            <MenuItem value="inactive">{t.models.stopped}</MenuItem>
          </Select>
        </FormControl>
      </GlassPanel>

      {/* Card view */}
      {viewMode === 'card' && (
        <Grid container spacing={2.5}>
          {filtered.map((model, i) => {
            const pool = inferPool(model.model_code);
            const freq = inferFreq(model.model_code);
            const color = POOL_COLORS[pool] || '#94a3b8';
            const neon = POOL_NEON[pool];
            return (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={model.id}>
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.06 }}
                >
                  <GlassPanel
                    glow
                    glowColor={color}
                    animate={false}
                    onClick={() => navigate(`/app/models/${model.model_code}`)}
                    sx={{
                      cursor: 'pointer',
                      transition: 'all 0.3s ease',
                      '&:hover': {
                        transform: 'translateY(-2px)',
                        boxShadow: `0 0 24px ${color}15`,
                      },
                    }}
                  >
                    {/* Header */}
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        mb: 1.5,
                      }}
                    >
                      <Box>
                        <Typography
                          sx={{ fontWeight: 700, color: '#e2e8f0', fontSize: '1rem', mb: 0.5 }}
                        >
                          {model.model_name}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {pool && (
                            <NeonChip
                              label={POOL_NAMES[pool] || pool}
                              size="small"
                              neonColor={neon || 'default'}
                            />
                          )}
                          {freq && (
                            <NeonChip
                              label={FREQ_LABELS[freq] || freq}
                              size="small"
                              neonColor="indigo"
                            />
                          )}
                          <NeonChip label={`v${model.version}`} size="small" neonColor="default" />
                        </Box>
                      </Box>
                      <IconButton
                        size="small"
                        onClick={(e) => handleMenuOpen(e, model)}
                        sx={{ color: '#64748b' }}
                      >
                        <MoreVertIcon fontSize="small" />
                      </IconButton>
                    </Box>

                    {/* Description */}
                    {model.description && (
                      <Typography
                        variant="body2"
                        sx={{
                          color: '#64748b',
                          mb: 1.5,
                          lineHeight: 1.4,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {model.description}
                      </Typography>
                    )}

                    {/* Key metrics */}
                    <Box sx={{ display: 'flex', gap: 2, mb: 1.5 }}>
                      <Box>
                        <Typography variant="caption" sx={{ color: '#64748b' }}>
                          {t.models.annualReturn}
                        </Typography>
                        <Typography sx={{ fontWeight: 600, color: '#22d3ee', fontSize: '0.9rem' }}>
                          {fmt(model.ic_mean, true)}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" sx={{ color: '#64748b' }}>
                          {t.models.sharpe}
                        </Typography>
                        <Typography sx={{ fontWeight: 600, color: '#8b5cf6', fontSize: '0.9rem' }}>
                          {fmt(model.ic_ir)}
                        </Typography>
                      </Box>
                    </Box>

                    {/* Footer */}
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        pt: 1.5,
                        borderTop: '1px solid rgba(148, 163, 184, 0.08)',
                      }}
                    >
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        {model.updated_at?.slice(0, 10)}
                      </Typography>
                      <NeonChip
                        label={model.status === 'active' ? t.models.running : t.models.stopped}
                        size="small"
                        neonColor={model.status === 'active' ? 'green' : 'default'}
                      />
                    </Box>
                  </GlassPanel>
                </motion.div>
              </Grid>
            );
          })}
          {filtered.length === 0 && (
            <Grid size={12}>
              <Typography sx={{ textAlign: 'center', color: '#64748b', py: 4 }}>
                暂无模型数据
              </Typography>
            </Grid>
          )}
        </Grid>
      )}

      {/* Table view */}
      {viewMode === 'table' && (
        <GlassPanel animate={false}>
          <GlassTable>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>模型名称</TableCell>
                  <TableCell>代码</TableCell>
                  <TableCell>股票池</TableCell>
                  <TableCell>频率</TableCell>
                  <TableCell>版本</TableCell>
                  <TableCell>状态</TableCell>
                  <TableCell>更新时间</TableCell>
                  <TableCell align="right">操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filtered.map((model) => {
                  const pool = inferPool(model.model_code);
                  const freq = inferFreq(model.model_code);
                  return (
                    <TableRow
                      key={model.id}
                      hover
                      onClick={() => navigate(`/app/models/${model.model_code}`)}
                      sx={{ cursor: 'pointer' }}
                    >
                      <TableCell sx={{ fontWeight: 600, color: '#e2e8f0' }}>
                        {model.model_name}
                      </TableCell>
                      <TableCell
                        sx={{ fontFamily: 'monospace', color: '#94a3b8', fontSize: '0.8rem' }}
                      >
                        {model.model_code}
                      </TableCell>
                      <TableCell>
                        {pool ? (
                          <NeonChip
                            label={POOL_NAMES[pool] || pool}
                            size="small"
                            neonColor={POOL_NEON[pool] || 'default'}
                          />
                        ) : (
                          '-'
                        )}
                      </TableCell>
                      <TableCell>{freq ? FREQ_LABELS[freq] || freq : '-'}</TableCell>
                      <TableCell>{model.version}</TableCell>
                      <TableCell>
                        <NeonChip
                          label={model.status === 'active' ? t.models.running : t.models.stopped}
                          size="small"
                          neonColor={model.status === 'active' ? 'green' : 'default'}
                        />
                      </TableCell>
                      <TableCell sx={{ color: '#64748b', fontSize: '0.85rem' }}>
                        {model.updated_at?.slice(0, 10)}
                      </TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={(e) => handleMenuOpen(e, model)}
                          sx={{ color: '#64748b' }}
                        >
                          <MoreVertIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {filtered.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      暂无模型数据
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </GlassTable>
        </GlassPanel>
      )}

      {/* Context menu */}
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={handleMenuClose}
        PaperProps={{
          sx: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(148, 163, 184, 0.15)',
            backdropFilter: 'blur(16px)',
          },
        }}
      >
        <MenuItem
          onClick={() => {
            handleMenuClose();
            if (menuModel) navigate(`/app/models/${menuModel.model_code}`);
          }}
        >
          {t.models.viewDetail}
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <ContentCopyIcon sx={{ fontSize: 16, mr: 1 }} /> {t.models.copyModel}
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <AssessmentIcon sx={{ fontSize: 16, mr: 1 }} /> {t.models.runBacktest}
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <FileDownloadIcon sx={{ fontSize: 16, mr: 1 }} /> {t.models.export}
        </MenuItem>
      </Menu>

      <Snackbar
        open={!!error}
        autoHideDuration={3000}
        onClose={() => setError('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );
}
