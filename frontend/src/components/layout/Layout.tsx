import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Typography,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Drawer,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  Snackbar,
  Alert,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CloseIcon from '@mui/icons-material/Close';
import DashboardIcon from '@mui/icons-material/Dashboard';
import FunctionsIcon from '@mui/icons-material/Functions';
import AssessmentIcon from '@mui/icons-material/Assessment';
import BarChartIcon from '@mui/icons-material/BarChart';
import TimelineIcon from '@mui/icons-material/Timeline';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import MonitorIcon from '@mui/icons-material/Monitor';
import NotificationsIcon from '@mui/icons-material/Notifications';
import SettingsIcon from '@mui/icons-material/Settings';
import PersonIcon from '@mui/icons-material/Person';
import LogoutIcon from '@mui/icons-material/Logout';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useAuth } from '@/contexts/AuthContext';
import ComplianceModal from '@/components/compliance/ComplianceModal';
import { Logo } from '@/components/ui';

const SIDEBAR_W = 200;

const NAV_ITEMS = [
  { key: '/app/dashboard', label: '工作台', icon: <DashboardIcon /> },
  { key: '/app/factors', label: '因子研究', icon: <FunctionsIcon /> },
  { key: '/app/models', label: '模型管理', icon: <AssessmentIcon /> },
  { key: '/app/backtests', label: '策略回测', icon: <BarChartIcon /> },
  { key: '/app/timing', label: '择时信号', icon: <TimelineIcon /> },
  { key: '/app/portfolios', label: '组合管理', icon: <AccountBalanceIcon /> },
  { key: '/app/monitor', label: '监控告警', icon: <MonitorIcon /> },
  { key: '/app/events', label: '事件中心', icon: <NotificationsIcon /> },
  { key: '/app/settings', label: '设置', icon: <SettingsIcon /> },
];

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  const handleLogout = () => {
    setUserMenuAnchor(null);
    logout();
    navigate('/login');
    setSnackbar({ open: true, message: '已退出登录', severity: 'success' });
  };

  const isActive = (path: string) => {
    if (path === '/app/settings') return location.pathname.startsWith(path);
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  const sidebarContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo */}
      <Box sx={{ px: 3, py: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Logo size={28} />
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: '0.9rem',
            background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            letterSpacing: '0.04em',
          }}
        >
          QuantPro
        </Typography>
      </Box>

      {/* Navigation */}
      <List sx={{ flex: 1, px: 2, py: 1 }}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.key);
          return (
            <ListItemButton
              key={item.key}
              onClick={() => {
                navigate(item.key);
                setMobileOpen(false);
              }}
              sx={{
                borderRadius: 2,
                mb: 1,
                minHeight: 48,
                px: 2.5,
                backgroundColor: active ? 'rgba(34, 211, 238, 0.06)' : 'transparent',
                borderLeft: active ? '2px solid #22d3ee' : '2px solid transparent',
                '&:hover': {
                  backgroundColor: active
                    ? 'rgba(34, 211, 238, 0.08)'
                    : 'rgba(148, 163, 184, 0.03)',
                },
                transition: 'all 0.2s ease',
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 36,
                  color: active ? '#22d3ee' : '#64748b',
                  transition: 'color 0.2s',
                }}
              >
                {item.icon}
              </ListItemIcon>
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
            </ListItemButton>
          );
        })}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* Desktop sidebar */}
      <Box
        sx={{
          width: SIDEBAR_W,
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 1200,
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          backdropFilter: 'blur(20px)',
          backgroundColor: 'rgba(3, 7, 18, 0.92)',
          borderRight: '1px solid rgba(148, 163, 184, 0.06)',
          overflow: 'auto',
        }}
      >
        {sidebarContent}
      </Box>

      {/* Main content area */}
      <Box
        sx={{
          flex: 1,
          ml: { xs: 0, md: `${SIDEBAR_W}px` },
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}
      >
        {/* Top bar */}
        <Box
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 3,
            py: 1.5,
            backdropFilter: 'blur(20px)',
            backgroundColor: 'rgba(10, 14, 26, 0.7)',
            borderBottom: '1px solid rgba(148, 163, 184, 0.08)',
          }}
        >
          {/* Mobile menu button */}
          <IconButton
            sx={{ display: { xs: 'flex', md: 'none' }, color: '#e2e8f0' }}
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon />
          </IconButton>

          {/* Spacer for desktop */}
          <Box sx={{ display: { xs: 'none', md: 'block' } }} />

          {/* User menu */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton
              onClick={(e) => setUserMenuAnchor(e.currentTarget)}
              sx={{ color: '#94a3b8' }}
            >
              <Avatar
                sx={{
                  width: 32,
                  height: 32,
                  bgcolor: 'rgba(34, 211, 238, 0.15)',
                  color: '#22d3ee',
                  fontSize: '0.85rem',
                }}
              >
                {user?.username?.charAt(0) || 'U'}
              </Avatar>
              <ExpandMoreIcon sx={{ fontSize: 16 }} />
            </IconButton>
            <Menu
              anchorEl={userMenuAnchor}
              open={Boolean(userMenuAnchor)}
              onClose={() => setUserMenuAnchor(null)}
              PaperProps={{ sx: { mt: 1, minWidth: 160 } }}
            >
              <MenuItem
                onClick={() => {
                  setUserMenuAnchor(null);
                  navigate('/app/settings');
                }}
              >
                <ListItemIcon sx={{ color: '#94a3b8' }}>
                  <PersonIcon fontSize="small" />
                </ListItemIcon>
                个人设置
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}>
                <ListItemIcon sx={{ color: '#f43f5e' }}>
                  <LogoutIcon fontSize="small" />
                </ListItemIcon>
                退出登录
              </MenuItem>
            </Menu>
          </Box>
        </Box>

        {/* Mobile drawer */}
        <Drawer
          anchor="left"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          PaperProps={{
            sx: { backgroundColor: 'rgba(3,7,18,0.95)', backdropFilter: 'blur(20px)', width: 240 },
          }}
        >
          <Box sx={{ p: 2, display: 'flex', justifyContent: 'flex-end' }}>
            <IconButton onClick={() => setMobileOpen(false)} sx={{ color: '#e2e8f0' }}>
              <CloseIcon />
            </IconButton>
          </Box>
          {sidebarContent}
        </Drawer>

        {/* Page content */}
        <Box component="main" sx={{ flex: 1, p: { xs: 2, md: 3 } }}>
          <Outlet />
        </Box>

        {/* Footer */}
        <Box component="footer" sx={{ py: 3, px: 4, textAlign: 'center' }}>
          <Typography sx={{ color: '#475569', fontSize: '0.75rem' }}>
            A股多因子增强策略平台 ©{new Date().getFullYear()} · 仅供研究使用，不构成投资建议
          </Typography>
        </Box>
      </Box>

      <ComplianceModal storageKey="compliance_workbench_shown" />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
