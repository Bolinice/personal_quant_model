import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Grid, Snackbar, Alert } from '@mui/material';
import { motion } from 'framer-motion';
import FunctionsIcon from '@mui/icons-material/Functions';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { MetricCard, GlassPanel } from '@/components/ui';
import { factorApi, modelApi } from '@/api';
import { useT } from '@/i18n';

export default function Dashboard() {
  const navigate = useNavigate();
  const t = useT();
  const [stats, setStats] = useState({ factors: 0, models: 0 });
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      factorApi.list({ limit: 1 }).then((res) => ({ factors: res.data.length })).catch(() => ({ factors: 0 })),
      modelApi.list({ limit: 1 }).then((res) => ({ models: res.data.length })).catch(() => ({ models: 0 })),
    ]).then((results) => {
      const merged = results.reduce((acc, r) => ({ ...acc, ...r }), {} as Partial<typeof stats>);
      setStats((s) => ({ ...s, ...merged }));
    });
  }, []);

  const cards = [
    { title: t.dashboard.factorCount, value: stats.factors, icon: <FunctionsIcon />, color: '#22d3ee', path: '/app/factors' },
    { title: t.dashboard.modelCount, value: stats.models, icon: <ModelTrainingIcon />, color: '#8b5cf6', path: '/app/models' },
  ];

  const quickActions = [
    { label: t.dashboard.factorMgmt, desc: t.dashboard.factorDesc, path: '/app/factors', color: '#22d3ee' },
    { label: t.dashboard.modelMgmt, desc: t.dashboard.modelDesc, path: '/app/models', color: '#8b5cf6' },
  ];

  return (
    <Box>
      {/* Gradient title */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Typography
          variant="h3"
          sx={{
            fontWeight: 800,
            mb: 1,
            background: 'linear-gradient(135deg, #e2e8f0 0%, #22d3ee 50%, #8b5cf6 100%)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            letterSpacing: '-0.03em',
          }}
        >
          {t.dashboard.title}
        </Typography>
        <Typography variant="body1" sx={{ color: '#64748b', mb: 4 }}>
          {t.dashboard.subtitle}
        </Typography>
      </motion.div>

      {/* Metric cards */}
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        {cards.map((card, i) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={card.title}>
            <Box onClick={() => navigate(card.path)} sx={{ cursor: 'pointer' }}>
              <MetricCard
                label={card.title}
                value={card.value}
                color={card.color}
                icon={card.icon}
                delay={i * 0.1}
              />
            </Box>
          </Grid>
        ))}
      </Grid>

      {/* Quick actions */}
      <Typography variant="h6" sx={{ fontWeight: 600, color: '#94a3b8', mb: 2, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {t.dashboard.quickActions}
      </Typography>
      <Grid container spacing={2}>
        {quickActions.map((action, i) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={action.label}>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.3 + i * 0.06 }}
            >
              <GlassPanel
                glow
                glowColor={action.color}
                animate={false}
                onClick={() => navigate(action.path)}
                sx={{
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  transition: 'all 0.3s ease',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: `0 0 24px ${action.color}15`,
                  },
                }}
              >
                <Box>
                  <Typography sx={{ fontWeight: 600, color: '#e2e8f0', fontSize: '0.95rem' }}>{action.label}</Typography>
                  <Typography variant="body2" sx={{ color: '#64748b', mt: 0.25 }}>{action.desc}</Typography>
                </Box>
                <ArrowForwardIcon sx={{ color: `${action.color}66`, transition: 'color 0.2s' }} />
              </GlassPanel>
            </motion.div>
          </Grid>
        ))}
      </Grid>

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError('')} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
      </Snackbar>
    </Box>
  );
}
