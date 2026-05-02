import { Box, Typography, Button, Breadcrumbs, Link } from '@mui/material';
import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: Array<{ label: string; path?: string }>;
  actions?: ReactNode;
  showBack?: boolean;
  backPath?: string;
}

export default function PageHeader({
  title,
  subtitle,
  breadcrumbs,
  actions,
  showBack = false,
  backPath,
}: PageHeaderProps) {
  const navigate = useNavigate();

  return (
    <Box sx={{ mb: 4 }}>
      {/* 面包屑导航 */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs
          separator={<NavigateNextIcon fontSize="small" sx={{ color: '#64748b' }} />}
          sx={{ mb: 2 }}
        >
          {breadcrumbs.map((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1;
            return isLast ? (
              <Typography key={index} sx={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                {crumb.label}
              </Typography>
            ) : (
              <Link
                key={index}
                onClick={() => crumb.path && navigate(crumb.path)}
                sx={{
                  color: '#64748b',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  textDecoration: 'none',
                  '&:hover': { color: '#94a3b8' },
                }}
              >
                {crumb.label}
              </Link>
            );
          })}
        </Breadcrumbs>
      )}

      {/* 标题区域 */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 3,
          flexWrap: 'wrap',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1, minWidth: 0 }}>
          {/* 返回按钮 */}
          {showBack && (
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={() => (backPath ? navigate(backPath) : navigate(-1))}
              sx={{
                color: '#94a3b8',
                minWidth: 'auto',
                px: 2,
                py: 1,
                borderRadius: '10px',
                '&:hover': {
                  color: '#cbd5e1',
                  background: 'rgba(148, 163, 184, 0.08)',
                },
              }}
            >
              返回
            </Button>
          )}

          {/* 标题和副标题 */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <Typography
                variant="h4"
                sx={{
                  fontWeight: 700,
                  fontSize: { xs: '1.75rem', md: '2rem' },
                  background: 'linear-gradient(135deg, #f1f5f9 0%, #cbd5e1 100%)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  mb: subtitle ? 0.5 : 0,
                }}
              >
                {title}
              </Typography>
            </motion.div>
            {subtitle && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.1 }}
              >
                <Typography
                  sx={{
                    color: '#94a3b8',
                    fontSize: '0.875rem',
                    mt: 0.5,
                  }}
                >
                  {subtitle}
                </Typography>
              </motion.div>
            )}
          </Box>
        </Box>

        {/* 操作按钮区域 */}
        {actions && (
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Box
              sx={{
                display: 'flex',
                gap: 1.5,
                alignItems: 'center',
              }}
            >
              {actions}
            </Box>
          </motion.div>
        )}
      </Box>
    </Box>
  );
}
