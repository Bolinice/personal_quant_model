import { useState, type MouseEvent } from 'react';
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  Box, AppBar, Toolbar, Typography, List, ListItemButton,
  ListItemIcon, ListItemText, IconButton, Tooltip, Button, Collapse,
  Popover, Grid, Chip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import FunctionsIcon from '@mui/icons-material/Functions';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ListAltIcon from '@mui/icons-material/ListAlt';
import WidgetsIcon from '@mui/icons-material/Widgets';
import AssessmentIcon from '@mui/icons-material/Assessment';
import CardMembershipIcon from '@mui/icons-material/CardMembership';
import PaletteIcon from '@mui/icons-material/Palette';
import CheckIcon from '@mui/icons-material/Check';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedPage from './AnimatedPage';
import { Logo } from '@/components/ui';
import { useLang } from '@/i18n';
import { useBackground, CONSTELLATION_THEMES } from '@/components/background';

const COLLAPSED = 72;
const EXPANDED = 240;

const modelSubItems = [
  { labelKey: 'overview' as const, path: '/app/models/overview', icon: <DashboardIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'myModels' as const, path: '/app/models', icon: <ListAltIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'templates' as const, path: '/app/models/templates', icon: <WidgetsIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'backtests' as const, path: '/app/models/backtests', icon: <AssessmentIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'plan' as const, path: '/app/models/plan', icon: <CardMembershipIcon sx={{ fontSize: 20 }} /> },
];

export default function Layout() {
  const [expanded, setExpanded] = useState(true);
  const [modelsOpen, setModelsOpen] = useState(true);
  const [settingsAnchor, setSettingsAnchor] = useState<HTMLElement | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { lang, t, toggleLang } = useLang();
  const { theme: bgTheme, setThemeById } = useBackground();
  const width = expanded ? EXPANDED : COLLAPSED;

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  const isModelsActive = location.pathname.startsWith('/app/models');

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <Box
        component={motion.div}
        animate={{ width }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        sx={{
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          zIndex: 1200,
          backdropFilter: 'blur(20px)',
          backgroundColor: 'rgba(10, 14, 26, 0.85)',
          borderRight: '1px solid rgba(148, 163, 184, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Logo area */}
        <Box
          component={Link}
          to="/"
          sx={{ px: 2, py: 2, display: 'flex', alignItems: 'center', gap: 1.5, minHeight: 64, textDecoration: 'none', color: 'inherit' }}
        >
          <Logo />
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.2 }}
                style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}
              >
                <Typography sx={{ fontWeight: 700, fontSize: '1rem', background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)', backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  {t.brand.name}
                </Typography>
              </motion.div>
            )}
          </AnimatePresence>
        </Box>

        {/* Nav items */}
        <List sx={{ flex: 1, px: 1, py: 1, overflow: 'auto' }}>
          {/* Factor management */}
          <Tooltip title={expanded ? '' : t.nav.factors} placement="right" arrow>
            <ListItemButton
              onClick={() => navigate('/app/factors')}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                minHeight: 44,
                px: 1.5,
                justifyContent: expanded ? 'flex-start' : 'center',
                backgroundColor: isActive('/app/factors') ? 'rgba(34, 211, 238, 0.1)' : 'transparent',
                border: isActive('/app/factors') ? '1px solid rgba(34, 211, 238, 0.2)' : '1px solid transparent',
                '&:hover': {
                  backgroundColor: isActive('/app/factors') ? 'rgba(34, 211, 238, 0.12)' : 'rgba(148, 163, 184, 0.06)',
                },
                transition: 'all 0.2s ease',
              }}
            >
              <ListItemIcon sx={{ minWidth: expanded ? 40 : 0, color: isActive('/app/factors') ? '#22d3ee' : '#64748b', transition: 'color 0.2s ease' }}>
                <FunctionsIcon />
              </ListItemIcon>
              <AnimatePresence>
                {expanded && (
                  <motion.div
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: 'auto' }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.2 }}
                    style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}
                  >
                    <ListItemText
                      primary={t.nav.factors}
                      sx={{ '& .MuiListItemText-primary': { fontWeight: isActive('/app/factors') ? 600 : 400, color: isActive('/app/factors') ? '#e2e8f0' : '#94a3b8', fontSize: '0.875rem' } }}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </ListItemButton>
          </Tooltip>

          {/* Model management — expandable */}
          <Tooltip title={expanded ? '' : t.nav.modelMgmt} placement="right" arrow>
            <ListItemButton
              onClick={() => {
                if (!expanded) {
                  setExpanded(true);
                  setModelsOpen(true);
                } else {
                  setModelsOpen(!modelsOpen);
                }
              }}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                minHeight: 44,
                px: 1.5,
                justifyContent: expanded ? 'flex-start' : 'center',
                backgroundColor: isModelsActive ? 'rgba(34, 211, 238, 0.1)' : 'transparent',
                border: isModelsActive ? '1px solid rgba(34, 211, 238, 0.2)' : '1px solid transparent',
                '&:hover': {
                  backgroundColor: isModelsActive ? 'rgba(34, 211, 238, 0.12)' : 'rgba(148, 163, 184, 0.06)',
                },
                transition: 'all 0.2s ease',
              }}
            >
              <ListItemIcon sx={{ minWidth: expanded ? 40 : 0, color: isModelsActive ? '#22d3ee' : '#64748b', transition: 'color 0.2s ease' }}>
                <ModelTrainingIcon />
              </ListItemIcon>
              <AnimatePresence>
                {expanded && (
                  <motion.div
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: 'auto' }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.2 }}
                    style={{ overflow: 'hidden', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flex: 1 }}
                  >
                    <ListItemText
                      primary={t.nav.modelMgmt}
                      sx={{ '& .MuiListItemText-primary': { fontWeight: isModelsActive ? 600 : 400, color: isModelsActive ? '#e2e8f0' : '#94a3b8', fontSize: '0.875rem' } }}
                    />
                    {modelsOpen ? <ExpandLessIcon sx={{ fontSize: 18, color: '#64748b' }} /> : <ExpandMoreIcon sx={{ fontSize: 18, color: '#64748b' }} />}
                  </motion.div>
                )}
              </AnimatePresence>
            </ListItemButton>
          </Tooltip>

          {/* Model sub-items */}
          <Collapse in={modelsOpen && expanded} timeout="auto" unmountOnExit>
            <List sx={{ pl: 2 }}>
              {modelSubItems.map((item) => {
                const active = item.path === '/app/models'
                  ? location.pathname === '/app/models'
                  : isActive(item.path);
                const label = t.models[item.labelKey];
                return (
                  <Tooltip key={item.path} title={label} placement="right" arrow>
                    <ListItemButton
                      onClick={() => navigate(item.path)}
                      sx={{
                        borderRadius: 2,
                        mb: 0.25,
                        minHeight: 36,
                        px: 1.5,
                        justifyContent: 'flex-start',
                        backgroundColor: active ? 'rgba(34, 211, 238, 0.08)' : 'transparent',
                        border: active ? '1px solid rgba(34, 211, 238, 0.15)' : '1px solid transparent',
                        '&:hover': {
                          backgroundColor: active ? 'rgba(34, 211, 238, 0.1)' : 'rgba(148, 163, 184, 0.04)',
                        },
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 32, color: active ? '#22d3ee' : '#64748b', '& .MuiSvgIcon-root': { fontSize: 18 } }}>
                        {item.icon}
                      </ListItemIcon>
                      <ListItemText
                        primary={label}
                        sx={{ '& .MuiListItemText-primary': { fontWeight: active ? 600 : 400, color: active ? '#e2e8f0' : '#94a3b8', fontSize: '0.8rem' } }}
                      />
                    </ListItemButton>
                  </Tooltip>
                );
              })}
            </List>
          </Collapse>
        </List>

        {/* Collapse toggle */}
        <Box sx={{ p: 1, borderTop: '1px solid rgba(148, 163, 184, 0.08)' }}>
          <ListItemButton
            onClick={() => setExpanded(!expanded)}
            sx={{ borderRadius: 2, justifyContent: 'center', minHeight: 40 }}
          >
            <motion.div
              animate={{ rotate: expanded ? 0 : 180 }}
              transition={{ duration: 0.3 }}
            >
              <ChevronLeftIcon sx={{ color: '#64748b' }} />
            </motion.div>
          </ListItemButton>
        </Box>
      </Box>

      {/* Main content */}
      <Box
        component={motion.div}
        animate={{ marginLeft: width }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          overflow: 'hidden',
        }}
      >
        {/* Top bar */}
        <AppBar
          position="static"
          elevation={0}
          sx={{
            backdropFilter: 'blur(20px)',
            backgroundColor: 'rgba(10, 14, 26, 0.7)',
            borderBottom: '1px solid rgba(148, 163, 184, 0.08)',
          }}
        >
          <Toolbar sx={{ minHeight: '56px !important' }}>
            <IconButton
              color="inherit"
              edge="start"
              onClick={() => setExpanded(!expanded)}
              sx={{ mr: 2, display: { sm: 'none' } }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="body2" sx={{ color: '#64748b', fontWeight: 500, flex: 1 }}>
              {t.brand.name}
            </Typography>
            <Tooltip title="背景设置" arrow>
              <IconButton
                onClick={(e: MouseEvent<HTMLElement>) => setSettingsAnchor(e.currentTarget)}
                sx={{ color: '#94a3b8', '&:hover': { color: '#22d3ee' } }}
              >
                <PaletteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Popover
              open={Boolean(settingsAnchor)}
              anchorEl={settingsAnchor}
              onClose={() => setSettingsAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              slotProps={{
                paper: {
                  sx: {
                    mt: 1, width: 360, p: 2,
                    background: 'rgba(15, 23, 42, 0.95)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(148, 163, 184, 0.12)',
                    borderRadius: 3,
                    boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)',
                  },
                },
              }}
            >
              <Typography sx={{ fontWeight: 600, color: '#e2e8f0', mb: 0.5, fontSize: '0.95rem' }}>
                背景主题
              </Typography>
              <Typography sx={{ color: '#64748b', fontSize: '0.75rem', mb: 2 }}>
                选择星座背景，匹配不同时段
              </Typography>
              <Grid container spacing={1}>
                {CONSTELLATION_THEMES.map((ct) => {
                  const active = bgTheme.id === ct.id;
                  return (
                    <Grid size={6} key={ct.id}>
                      <Box
                        onClick={() => { setThemeById(ct.id); setSettingsAnchor(null); }}
                        sx={{
                          p: 1.5, borderRadius: 2, cursor: 'pointer',
                          bgcolor: active ? 'rgba(34, 211, 238, 0.08)' : 'rgba(148, 163, 184, 0.04)',
                          border: active ? '1px solid rgba(34, 211, 238, 0.3)' : '1px solid rgba(148, 163, 184, 0.08)',
                          transition: 'all 0.2s ease',
                          '&:hover': {
                            bgcolor: active ? 'rgba(34, 211, 238, 0.1)' : 'rgba(148, 163, 184, 0.08)',
                            borderColor: active ? 'rgba(34, 211, 238, 0.4)' : 'rgba(148, 163, 184, 0.15)',
                          },
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                          <Typography sx={{ fontSize: '0.85rem', fontWeight: 600, color: active ? '#22d3ee' : '#e2e8f0' }}>
                            {ct.icon} {ct.name}
                          </Typography>
                          {active && <CheckIcon sx={{ fontSize: 14, color: '#22d3ee' }} />}
                        </Box>
                        <Typography sx={{ fontSize: '0.7rem', color: '#64748b' }}>
                          {ct.timeLabel}
                        </Typography>
                        {/* Mini color preview */}
                        <Box sx={{ display: 'flex', gap: 0.5, mt: 1 }}>
                          <Box sx={{ width: 16, height: 8, borderRadius: 0.5, bgcolor: ct.bgColor, border: '1px solid rgba(148,163,184,0.15)' }} />
                          <Box sx={{ width: 16, height: 8, borderRadius: 0.5, background: `rgb(${ct.starColor.join(',')})` }} />
                          <Box sx={{ width: 16, height: 8, borderRadius: 0.5, background: `rgb(${ct.shootingColor.join(',')})` }} />
                        </Box>
                      </Box>
                    </Grid>
                  );
                })}
              </Grid>
            </Popover>
            <Button
              size="small"
              onClick={toggleLang}
              sx={{
                color: '#94a3b8', fontSize: '0.75rem', textTransform: 'none',
                minWidth: 36, px: 1, py: 0.25,
                border: '1px solid rgba(148,163,184,0.2)', borderRadius: 1,
                '&:hover': { borderColor: 'rgba(34,211,238,0.4)', color: '#22d3ee' },
              }}
            >
              中/EN
            </Button>
            <Button
              component={Link}
              to="/"
              startIcon={<ArrowBackIcon />}
              size="small"
              sx={{ color: '#94a3b8', textTransform: 'none', ml: 1 }}
            >
              {t.btn.backToSite}
            </Button>
          </Toolbar>
        </AppBar>

        {/* Page content */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
          <AnimatedPage>
            <Outlet />
          </AnimatedPage>
        </Box>
      </Box>
    </Box>
  );
}
