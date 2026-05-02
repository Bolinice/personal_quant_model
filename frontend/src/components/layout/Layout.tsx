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
  InputBase,
  Badge,
  Tooltip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CloseIcon from '@mui/icons-material/Close';
import DashboardIcon from '@mui/icons-material/Dashboard';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ScienceIcon from '@mui/icons-material/Science';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import StorageIcon from '@mui/icons-material/Storage';
import NotificationsIcon from '@mui/icons-material/Notifications';
import SettingsIcon from '@mui/icons-material/Settings';
import PersonIcon from '@mui/icons-material/Person';
import LogoutIcon from '@mui/icons-material/Logout';
import SearchIcon from '@mui/icons-material/Search';
import { useAuth } from '@/contexts/AuthContext';
import ComplianceModal from '@/components/compliance/ComplianceModal';
import { Logo } from '@/components/ui';

const SIDEBAR_W = 240;

// 重新组织的导航结构 - 更清晰的分组
const NAV_GROUPS = [
  {
    title: '核心功能',
    items: [
      { key: '/app/dashboard', label: '工作台', icon: <DashboardIcon />, tourId: 'nav-dashboard' },
      { key: '/app/strategies', label: '策略中心', icon: <TrendingUpIcon />, tourId: 'nav-strategies' },
      { key: '/app/backtests', label: '回测实验室', icon: <ScienceIcon />, tourId: 'nav-backtests' },
      { key: '/app/portfolios', label: '组合管理', icon: <AccountBalanceWalletIcon />, tourId: 'nav-portfolios' },
    ],
  },
  {
    title: '辅助功能',
    items: [
      { key: '/app/data', label: '数据中心', icon: <StorageIcon />, tourId: 'nav-data' },
      { key: '/app/monitor', label: '监控告警', icon: <NotificationsIcon />, tourId: 'nav-monitor' },
    ],
  },
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
      {/* Logo区域 - 更精致 */}
      <Box
        sx={{
          px: 3,
          py: 3.5,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          cursor: 'pointer',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            opacity: 0.85,
            transform: 'translateX(2px)',
          },
        }}
        onClick={() => navigate('/')}
      >
        <Logo size={32} />
        <Box>
          <Typography
            sx={{
              fontWeight: 700,
              fontSize: '1.125rem',
              background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: '0.02em',
              lineHeight: 1.2,
            }}
          >
            银河漫游
          </Typography>
          <Typography
            sx={{
              fontSize: '0.6875rem',
              color: '#64748b',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              mt: 0.25,
            }}
          >
            Quant Platform
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'rgba(148, 163, 184, 0.06)', mx: 2 }} />

      {/* 导航列表 - 分组显示 */}
      <Box sx={{ flex: 1, px: 2, py: 2, overflowY: 'auto' }}>
        {NAV_GROUPS.map((group, groupIndex) => (
          <Box key={group.title} sx={{ mb: groupIndex < NAV_GROUPS.length - 1 ? 3 : 0 }}>
            <Typography
              sx={{
                px: 2,
                py: 1,
                fontSize: '0.6875rem',
                fontWeight: 600,
                color: '#64748b',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              {group.title}
            </Typography>
            <List sx={{ py: 0.5 }}>
              {group.items.map((item) => {
                const active = isActive(item.key);
                return (
                  <ListItemButton
                    key={item.key}
                    data-tour={item.tourId}
                    onClick={() => {
                      navigate(item.key);
                      setMobileOpen(false);
                    }}
                    sx={{
                      borderRadius: '12px',
                      mb: 0.5,
                      minHeight: 44,
                      px: 2,
                      position: 'relative',
                      overflow: 'hidden',
                      backgroundColor: active
                        ? 'rgba(34, 211, 238, 0.06)'
                        : 'transparent',
                      borderLeft: active ? '2px solid #22d3ee' : '2px solid transparent',
                      '&:hover': {
                        backgroundColor: active
                          ? 'rgba(34, 211, 238, 0.08)'
                          : 'rgba(148, 163, 184, 0.03)',
                      },
                      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        minWidth: 40,
                        color: active ? '#818cf8' : '#64748b',
                        transition: 'color 0.2s',
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.label}
                      sx={{
                        '& .MuiListItemText-primary': {
                          fontWeight: active ? 600 : 500,
                          color: active ? '#f1f5f9' : '#94a3b8',
                          fontSize: '0.9375rem',
                          transition: 'color 0.2s',
                        },
                      }}
                    />
                  </ListItemButton>
                );
              })}
            </List>
          </Box>
        ))}
      </Box>

      <Divider sx={{ borderColor: 'rgba(148, 163, 184, 0.06)', mx: 2 }} />

      {/* 底部用户信息 */}
      <Box sx={{ p: 2 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            p: 1.5,
            borderRadius: '12px',
            background: 'rgba(102, 126, 234, 0.08)',
            border: '1px solid rgba(102, 126, 234, 0.15)',
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              background: 'rgba(102, 126, 234, 0.12)',
              borderColor: 'rgba(102, 126, 234, 0.25)',
            },
          }}
          onClick={(e) => setUserMenuAnchor(e.currentTarget)}
        >
          <Avatar
            sx={{
              width: 36,
              height: 36,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              fontSize: '0.875rem',
              fontWeight: 600,
            }}
          >
            {user?.username?.charAt(0).toUpperCase() || 'U'}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              sx={{
                fontSize: '0.875rem',
                fontWeight: 600,
                color: '#f1f5f9',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {user?.username || '用户'}
            </Typography>
            <Typography
              sx={{
                fontSize: '0.75rem',
                color: '#64748b',
              }}
            >
              在线
            </Typography>
          </Box>
          <SettingsIcon sx={{ fontSize: 18, color: '#64748b' }} />
        </Box>
      </Box>
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
          overflow: 'hidden',
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
        {/* Top bar - 增强功能 */}
        <Box
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 3,
            py: 2,
            backdropFilter: 'blur(20px)',
            backgroundColor: 'rgba(3, 7, 18, 0.8)',
            borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
          }}
        >
          {/* Mobile menu button */}
          <IconButton
            sx={{
              display: { xs: 'flex', md: 'none' },
              color: '#f1f5f9',
              '&:hover': { backgroundColor: 'rgba(102, 126, 234, 0.1)' },
            }}
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon />
          </IconButton>

          {/* 全局搜索 - 桌面端 */}
          <Box
            sx={{
              display: { xs: 'none', md: 'flex' },
              alignItems: 'center',
              gap: 1,
              px: 2,
              py: 1,
              borderRadius: '10px',
              backgroundColor: 'rgba(26, 26, 46, 0.6)',
              border: '1px solid rgba(102, 126, 234, 0.15)',
              width: 320,
              transition: 'all 0.2s',
              '&:hover': {
                borderColor: 'rgba(102, 126, 234, 0.3)',
                backgroundColor: 'rgba(26, 26, 46, 0.8)',
              },
              '&:focus-within': {
                borderColor: '#667eea',
                boxShadow: '0 0 0 3px rgba(102, 126, 234, 0.1)',
              },
            }}
          >
            <SearchIcon sx={{ fontSize: 18, color: '#64748b' }} />
            <InputBase
              placeholder="搜索策略、因子、回测..."
              sx={{
                flex: 1,
                fontSize: '0.875rem',
                color: '#f1f5f9',
                '& input::placeholder': {
                  color: '#64748b',
                  opacity: 1,
                },
              }}
            />
            <Typography
              sx={{
                fontSize: '0.6875rem',
                color: '#64748b',
                px: 1,
                py: 0.25,
                borderRadius: '4px',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                fontWeight: 600,
              }}
            >
              ⌘K
            </Typography>
          </Box>

          {/* 右侧操作区 */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* 通知中心 */}
            <Tooltip title="通知中心">
              <IconButton
                sx={{
                  color: '#94a3b8',
                  '&:hover': {
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    color: '#f1f5f9',
                  },
                }}
              >
                <Badge badgeContent={3} color="error">
                  <NotificationsIcon />
                </Badge>
              </IconButton>
            </Tooltip>

            {/* 设置 */}
            <Tooltip title="设置">
              <IconButton
                onClick={() => navigate('/app/settings')}
                sx={{
                  color: '#94a3b8',
                  '&:hover': {
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    color: '#f1f5f9',
                  },
                }}
              >
                <SettingsIcon />
              </IconButton>
            </Tooltip>

            {/* 用户菜单 */}
            <IconButton
              onClick={(e) => setUserMenuAnchor(e.currentTarget)}
              sx={{
                p: 0.5,
                '&:hover': { backgroundColor: 'rgba(102, 126, 234, 0.1)' },
              }}
            >
              <Avatar
                sx={{
                  width: 32,
                  height: 32,
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                }}
              >
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </Avatar>
            </IconButton>

            <Menu
              anchorEl={userMenuAnchor}
              open={Boolean(userMenuAnchor)}
              onClose={() => setUserMenuAnchor(null)}
              slotProps={{
                paper: {
                  sx: {
                    mt: 1,
                    minWidth: 200,
                    backdropFilter: 'blur(20px) saturate(180%)',
                    backgroundColor: 'rgba(26, 26, 46, 0.95)',
                    border: '1px solid rgba(102, 126, 234, 0.2)',
                  },
                },
              }}
            >
              <Box sx={{ px: 2, py: 1.5 }}>
                <Typography sx={{ fontSize: '0.875rem', fontWeight: 600, color: '#f1f5f9' }}>
                  {user?.username || '用户'}
                </Typography>
                <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
                  {user?.email || 'user@example.com'}
                </Typography>
              </Box>
              <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)' }} />
              <MenuItem
                onClick={() => {
                  setUserMenuAnchor(null);
                  navigate('/app/settings');
                }}
                sx={{
                  py: 1.5,
                  '&:hover': { backgroundColor: 'rgba(102, 126, 234, 0.1)' },
                }}
              >
                <ListItemIcon sx={{ color: '#94a3b8' }}>
                  <PersonIcon fontSize="small" />
                </ListItemIcon>
                <Typography sx={{ fontSize: '0.875rem' }}>个人设置</Typography>
              </MenuItem>
              <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)' }} />
              <MenuItem
                onClick={handleLogout}
                sx={{
                  py: 1.5,
                  '&:hover': { backgroundColor: 'rgba(239, 68, 68, 0.1)' },
                }}
              >
                <ListItemIcon sx={{ color: '#f87171' }}>
                  <LogoutIcon fontSize="small" />
                </ListItemIcon>
                <Typography sx={{ fontSize: '0.875rem', color: '#f87171' }}>退出登录</Typography>
              </MenuItem>
            </Menu>
          </Box>
        </Box>

        {/* Mobile drawer */}
        <Drawer
          anchor="left"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          slotProps={{
            paper: {
              sx: {
                backgroundColor: 'rgba(15, 12, 41, 0.98)',
                backdropFilter: 'blur(24px) saturate(180%)',
                width: 280,
                borderRight: '1px solid rgba(102, 126, 234, 0.2)',
              },
            },
          }}
        >
          <Box sx={{ p: 2, display: 'flex', justifyContent: 'flex-end' }}>
            <IconButton
              onClick={() => setMobileOpen(false)}
              sx={{
                color: '#f1f5f9',
                '&:hover': { backgroundColor: 'rgba(102, 126, 234, 0.1)' },
              }}
            >
              <CloseIcon />
            </IconButton>
          </Box>
          {sidebarContent}
        </Drawer>

        {/* Page content */}
        <Box
          component="main"
          sx={{
            flex: 1,
            p: { xs: 2, md: 3 },
            position: 'relative',
            '&::before': {
              content: '""',
              position: 'fixed',
              top: 0,
              left: { xs: 0, md: SIDEBAR_W },
              right: 0,
              height: '40vh',
              background: 'radial-gradient(circle at 50% 0%, rgba(102, 126, 234, 0.08), transparent 70%)',
              pointerEvents: 'none',
              zIndex: 0,
            },
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Outlet />
          </Box>
        </Box>

        {/* Footer */}
        <Box
          component="footer"
          sx={{
            py: 3,
            px: 4,
            textAlign: 'center',
            borderTop: '1px solid rgba(102, 126, 234, 0.08)',
          }}
        >
          <Typography sx={{ color: '#64748b', fontSize: '0.75rem' }}>
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
          sx={{
            backdropFilter: 'blur(20px) saturate(180%)',
            backgroundColor: 'rgba(26, 26, 46, 0.95)',
            border: '1px solid rgba(102, 126, 234, 0.2)',
          }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
