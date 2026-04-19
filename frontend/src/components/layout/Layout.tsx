import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box, AppBar, Toolbar, Typography, List, ListItemButton,
  ListItemIcon, ListItemText, IconButton, Tooltip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import FunctionsIcon from '@mui/icons-material/Functions';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedPage from './AnimatedPage';

const COLLAPSED = 72;
const EXPANDED = 240;

const navItems = [
  { label: '因子管理', path: '/factors', icon: <FunctionsIcon /> },
  { label: '模型管理', path: '/models', icon: <ModelTrainingIcon /> },
];

export default function Layout() {
  const [expanded, setExpanded] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const width = expanded ? EXPANDED : COLLAPSED;

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

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
        <Box sx={{ px: 2, py: 2, display: 'flex', alignItems: 'center', gap: 1.5, minHeight: 64 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Typography sx={{ fontWeight: 800, fontSize: '1.1rem', color: '#030712' }}>Q</Typography>
          </Box>
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
                  量化策略平台
                </Typography>
              </motion.div>
            )}
          </AnimatePresence>
        </Box>

        {/* Nav items */}
        <List sx={{ flex: 1, px: 1, py: 1 }}>
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
                  <ListItemIcon sx={{
                    minWidth: expanded ? 40 : 0,
                    color: active ? '#22d3ee' : '#64748b',
                    transition: 'color 0.2s ease',
                  }}>
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
                          sx={{
                            '& .MuiListItemText-primary': {
                              fontWeight: active ? 600 : 400,
                              color: active ? '#e2e8f0' : '#94a3b8',
                              fontSize: '0.875rem',
                            },
                          }}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </ListItemButton>
              </Tooltip>
            );
          })}
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
            <Typography variant="body2" sx={{ color: '#64748b', fontWeight: 500 }}>
              A股多因子增强策略平台
            </Typography>
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
