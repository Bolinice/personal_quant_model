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
import TimelineIcon from '@mui/icons-material/Timeline';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import MonitorIcon from '@mui/icons-material/Monitor';
import NotificationsIcon from '@mui/icons-material/Notifications';
import PersonIcon from '@mui/icons-material/Person';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedPage from './AnimatedPage';
import { Logo } from '@/components/ui';
import { useLang } from '@/i18n';
import { useBackground, CONSTELLATION_THEMES } from '@/components/background';
import { useAuth } from '@/contexts/AuthContext';

const COLLAPSED = 72;
const EXPANDED = 240;

const modelSubItems = [
  { labelKey: 'overview' as const, path: '/app/models/overview', icon: <DashboardIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'myModels' as const, path: '/app/models', icon: <ListAltIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'templates' as const, path: '/app/models/templates', icon: <WidgetsIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'backtests' as const, path: '/app/models/backtests', icon: <AssessmentIcon sx={{ fontSize: 20 }} /> },
  { labelKey: 'plan' as const, path: '/app/models/plan', icon: <CardMembershipIcon sx={{ fontSize: 20 }} /> },
];

const navItems = [
  { path: '/app/dashboard', label: '仪表盘', icon: <DashboardIcon /> },
  { path: '/app/factors', label: '因子管理', icon: <FunctionsIcon /> },
  { path: '/app/backtests', label: '回测管理', icon: <AssessmentIcon /> },
  { path: '/app/timing', label: '择时管理', icon: <TimelineIcon /> },
  { path: '/app/portfolios', label: '组合管理', icon: <AccountBalanceIcon /> },
  { path: '/app/performance', label: '绩效分析', icon: <TrendingUpIcon /> },
  { path: '/app/monitor', label: '监控中心', icon: <MonitorIcon /> },
  { path: '/app/events', label: '事件中心', icon: <NotificationsIcon /> },
];

export default function Layout() {
  const [expanded, setExpanded] = useState(true);
  const [modelsOpen, setModelsOpen] = useState(true);
  const [settingsAnchor, setSettingsAnchor] = useState<HTMLElement | null>(null);
  const [userMenuAnchor, setUserMenuAnchor] = useState<HTMLElement | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { lang, t, toggleLang } = useLang();
  const { theme: bgTheme, setThemeById } = useBackground();
  const { user, logout } = useAuth();
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
          {navItems.map((item) => {
            const active = isActive(item.path);
            return (
              <Tooltip key={item.path} title={expanded ? '' : item.label} placement="right" arrow>
                <ListItemButton
                  onClick={() => navigate(item.path)}
                  sx={{
                    borderRadius: 2,
                    mb: 0.5,
                    minHeight: 44,
                    px: 1.5,
                    justifyContent: expanded ? 'flex-start' : 'center',
                    backgroundColor: active ? 'rgba(34, 211, 238, 0.1)' : 'transparent',
                    border: active ? '1px solid rgba(34, 211, 238, 0.2)' : '1px solid transparent',
                    '&:hover': {
                      backgroundColor: active ? 'rgba(34, 211, 238, 0.12)' : 'rgba(148, 163, 184, 0.06)',
                    },
                    transition: 'all 0.2s ease',
                  }}
                >
                  <ListItemIcon sx={{ minWidth: expanded ? 40 : 0, color: active ? '#22d3ee' : '#64748b', transition: 'color 0.2s ease' }}>
                    {item.icon}
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
                          primary={item.label}
                          sx={{ '& .MuiListItemText-primary': { fontWeight: active ? 600 : 400, color: active ? '#e2e8f0' : '#94a3b8', fontSize: '0.875rem' } }}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </ListItemButton>
              </Tooltip>
            );
          })}

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

        {/* User info */}
        <Box sx={{ p: 1.5, borderTop: '1px solid rgba(148, 163, 184, 0.08)' }}>
          <ListItemButton
            onClick={(e) => setUserMenuAnchor(e.currentTarget)}
            sx={{
              borderRadius: 2,
              px: 1,
              minHeight: 48,
              justifyContent: expanded ? 'flex-start' : 'center',
            }}
          >
            <Box sx={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'linear-gradient(135deg, #22d3ee 0%, #8b5cf6 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontWeight: 700, fontSize: '0.875rem', flexShrink: 0,
            }}>
              {user?.username?.charAt(0)?.toUpperCase() || 'U'}
            </Box>
            <AnimatePresence>
              {expanded && (
                <motion.div
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 'auto' }}
                  exit={{ opacity: 0, width: 0 }}
                  transition={{ duration: 0.2 }}
                  style={{ overflow: 'hidden', whiteSpace: 'nowrap', marginLeft: 12, flex: 1 }}
                >
                  <Typography sx={{ fontWeight: 600, fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.2 }}>
                    {user?.username || '用户'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.7rem', color: '#64748b', lineHeight: 1.2, mt: 0.25 }}>
                    {user?.email || ''}
                  </Typography>
                </motion.div>
              )}
            </AnimatePresence>
          </ListItemButton>

          {/* User dropdown menu */}
          <Popover
            open={Boolean(userMenuAnchor)}
            anchorEl={userMenuAnchor}
            onClose={() => setUserMenuAnchor(null)}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            transformOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            slotProps={{
              paper: {
                sx: {
                  mt: -1, minWidth: 160, py: 0.5,
                  background: 'rgba(15, 23, 42, 0.95)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(148, 163, 184, 0.12)',
                  borderRadius: 2,
                  boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)',
                },
              },
            }}
          >
            <ListItemButton
              onClick={() => { setUserMenuAnchor(null); navigate('/app/settings'); }}
              sx={{ px: 2, py: 1 }}
            >
              <SettingsIcon sx={{ fontSize: 18, color: '#94a3b8', mr: 1.5 }} />
              <Typography sx={{ fontSize: '0.85rem', color: '#e2e8f0' }}>个人设置</Typography>
            </ListItemButton>
            <ListItemButton
              onClick={() => { setUserMenuAnchor(null); logout(); navigate('/login'); }}
              sx={{ px: 2, py: 1 }}
            >
              <LogoutIcon sx={{ fontSize: 18, color: '#f43f5e', mr: 1.5 }} />
              <Typography sx={{ fontSize: '0.85rem', color: '#f43f5e' }}>退出登录</Typography>
            </ListItemButton>
          </Popover>
        </Box>

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
