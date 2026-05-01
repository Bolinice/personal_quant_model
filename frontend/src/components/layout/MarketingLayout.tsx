import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  IconButton,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CloseIcon from '@mui/icons-material/Close';
import HomeIcon from '@mui/icons-material/Home';
import FunctionsIcon from '@mui/icons-material/Functions';
import Inventory2Icon from '@mui/icons-material/Inventory2';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import InfoIcon from '@mui/icons-material/Info';
import LoginIcon from '@mui/icons-material/Login';
import { Logo } from '@/components/ui';
import { useLang } from '@/i18n';

const SIDEBAR_W = 200;

const NAV_ITEMS = [
  { key: 'home', path: '/', icon: <HomeIcon /> },
  { key: 'product', path: '/#features', icon: <Inventory2Icon /> },
  { key: 'models', path: '/app', icon: <FunctionsIcon /> },
  { key: 'pricing', path: '/pricing', icon: <TrendingUpIcon /> },
  { key: 'about', path: '/about', icon: <InfoIcon /> },
] as const;

export default function MarketingLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [visibleHash, setVisibleHash] = useState(window.location.hash);
  const { t, toggleLang } = useLang();

  // 监听滚动，根据当前视口位置确定活跃的导航项
  useEffect(() => {
    if (location.pathname !== '/') return;

    // 首页所有带 id 的 section，按页面顺序排列
    const sectionIds = ['features'];

    const handleScroll = () => {
      const scrollY = window.scrollY + window.innerHeight * 0.3;
      let activeHash = '';

      for (const id of sectionIds) {
        const el = document.getElementById(id);
        if (el && el.offsetTop <= scrollY) {
          activeHash = `#${id}`;
        }
      }

      setVisibleHash(activeHash);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll(); // 初始检查
    return () => window.removeEventListener('scroll', handleScroll);
  }, [location.pathname]);

  // Sync visible hash with location hash
  useEffect(() => {
    setVisibleHash(location.hash);
  }, [location.hash]);

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/' && !visibleHash;
    if (path.startsWith('/#')) return location.pathname === '/' && visibleHash === path.slice(1);
    return location.pathname.startsWith(path);
  };

  const handleNav = (path: string) => {
    setMobileOpen(false);
    if (path === '/') {
      // 首页：清除 hash 并滚回顶部
      if (location.pathname === '/' && !location.hash) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } else {
        navigate('/');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
      setVisibleHash('');
      return;
    }
    if (path.startsWith('/#')) {
      const hash = path.slice(1);
      if (location.pathname !== '/') {
        navigate('/' + hash);
        setTimeout(() => {
          const el = document.getElementById(path.slice(2));
          el?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      } else {
        // Use navigate instead of direct hash modification
        navigate(hash);
        const el = document.getElementById(path.slice(2));
        el?.scrollIntoView({ behavior: 'smooth' });
      }
    } else {
      navigate(path);
    }
  };

  const sidebarContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo + 品牌 — 点击回首页 */}
      <Box
        component={Link}
        to="/"
        sx={{
          px: 3,
          py: 3,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          textDecoration: 'none',
          color: 'inherit',
        }}
      >
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
          {t.brand.name}
        </Typography>
      </Box>

      {/* 导航标签页 */}
      <List sx={{ flex: 1, px: 2, py: 1 }}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.path);
          return (
            <ListItemButton
              key={item.path}
              onClick={() => handleNav(item.path)}
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
              <Box
                sx={{
                  mr: 2,
                  color: active ? '#22d3ee' : '#64748b',
                  display: 'flex',
                  transition: 'color 0.2s',
                }}
              >
                {item.icon}
              </Box>
              <ListItemText
                primary={t.nav[item.key as keyof typeof t.nav]}
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

      {/* 底部留白 */}
      <Box sx={{ flex: 1 }} />
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* 左侧导航 — 桌面端 */}
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

      {/* 右侧内容区 */}
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
        {/* 右上角: 语言切换 + 登录 */}
        <Box
          sx={{
            position: 'absolute',
            top: 16,
            right: 24,
            zIndex: 100,
            display: { xs: 'none', md: 'flex' },
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <Button
            size="small"
            onClick={toggleLang}
            sx={{
              color: '#94a3b8',
              fontSize: '0.8rem',
              textTransform: 'none',
              minWidth: 36,
              px: 1,
              py: 0.25,
              border: '1px solid rgba(148,163,184,0.2)',
              borderRadius: 1,
              '&:hover': { borderColor: 'rgba(34,211,238,0.4)', color: '#22d3ee' },
            }}
          >
            中/EN
          </Button>
          <Button
            size="small"
            startIcon={<LoginIcon />}
            onClick={() => navigate('/app')}
            sx={{ color: '#94a3b8', fontSize: '0.8rem', textTransform: 'none' }}
          >
            {t.btn.login}
          </Button>
        </Box>

        {/* 移动端: 顶部栏 */}
        <Box
          sx={{
            display: { xs: 'flex', md: 'none' },
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            height: 56,
            zIndex: 1200,
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2,
            backdropFilter: 'blur(20px)',
            backgroundColor: 'rgba(3, 7, 18, 0.92)',
            borderBottom: '1px solid rgba(148, 163, 184, 0.08)',
          }}
        >
          <Box
            component={Link}
            to="/"
            sx={{ display: 'flex', alignItems: 'center', gap: 1.5, textDecoration: 'none' }}
          >
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
              {t.brand.name}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button
              size="small"
              onClick={toggleLang}
              sx={{ color: '#94a3b8', fontSize: '0.75rem', minWidth: 28, px: 0.5 }}
            >
              中/EN
            </Button>
            <Button
              size="small"
              onClick={() => navigate('/app')}
              sx={{ color: '#94a3b8', fontSize: '0.75rem' }}
            >
              {t.btn.login}
            </Button>
            <IconButton sx={{ color: '#e2e8f0' }} onClick={() => setMobileOpen(true)}>
              <MenuIcon />
            </IconButton>
          </Box>
        </Box>

        <Drawer
          anchor="left"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          slotProps={{
            paper: {
              sx: { backgroundColor: 'rgba(3,7,18,0.95)', backdropFilter: 'blur(20px)', width: 240 },
            },
          }}
        >
          <Box sx={{ p: 2, display: 'flex', justifyContent: 'flex-end' }}>
            <IconButton onClick={() => setMobileOpen(false)} sx={{ color: '#e2e8f0' }}>
              <CloseIcon />
            </IconButton>
          </Box>
          {sidebarContent}
        </Drawer>

        {/* 页面内容 */}
        <Box
          component="main"
          sx={{
            flex: 1,
            pt: { xs: '56px', md: 0 },
            borderTop: {
              xs: '1px solid rgba(148, 163, 184, 0.06)',
              md: '1px solid rgba(148, 163, 184, 0.06)',
            },
          }}
        >
          <Outlet />
        </Box>

        {/* Footer: 只保留版权 */}
        <Box
          component="footer"
          sx={{
            py: 4,
            px: 4,
            textAlign: 'center',
          }}
        >
          <Typography sx={{ color: '#475569', fontSize: '0.75rem' }}>
            © {new Date().getFullYear()} {t.brand.name}. {t.footer.disclaimer}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
