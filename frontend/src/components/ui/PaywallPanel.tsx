import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import { motion } from 'framer-motion';

interface PaywallPanelProps {
  poolName: string;
  price?: number;
}

export default function PaywallPanel({ poolName, price = 199 }: PaywallPanelProps) {
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        position: 'relative',
        borderRadius: 3,
        overflow: 'hidden',
        minHeight: 400,
      }}
    >
      {/* Blur overlay */}
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          backdropFilter: 'blur(12px)',
          backgroundColor: 'rgba(10, 14, 26, 0.75)',
          zIndex: 1,
        }}
      />

      {/* Content card */}
      <Box
        component={motion.div}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        sx={{
          position: 'relative',
          zIndex: 2,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 400,
          gap: 2,
        }}
      >
        <Box
          sx={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #f59e0b, #f43f5e)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            mb: 1,
          }}
        >
          <LockIcon sx={{ fontSize: 32, color: '#030712' }} />
        </Box>

        <Typography
          variant="h5"
          sx={{
            fontWeight: 700,
            background: 'linear-gradient(135deg, #f59e0b, #f43f5e)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          {poolName} 策略报告
        </Typography>

        <Typography sx={{ color: '#94a3b8', textAlign: 'center', maxWidth: 400 }}>
          解锁{poolName}增强策略的完整报告，包含持仓评分、策略表现、风险指标等核心数据
        </Typography>

        <Box
          sx={{
            mt: 1,
            px: 3,
            py: 1.5,
            borderRadius: 2,
            border: '1px solid rgba(245, 158, 11, 0.3)',
            background: 'rgba(245, 158, 11, 0.08)',
          }}
        >
          <Typography
            sx={{ fontWeight: 700, color: '#f59e0b', fontSize: '2rem', textAlign: 'center' }}
          >
            ¥{price}
            <Typography component="span" sx={{ fontSize: '0.875rem', color: '#94a3b8', ml: 0.5 }}>
              /月
            </Typography>
          </Typography>
        </Box>

        <Button
          variant="contained"
          size="large"
          onClick={() => navigate('/subscribe')}
          sx={{
            mt: 1,
            px: 6,
            py: 1.5,
            background: 'linear-gradient(135deg, #f59e0b, #f43f5e)',
            borderRadius: 2,
            fontWeight: 700,
            fontSize: '1rem',
            '&:hover': {
              background: 'linear-gradient(135deg, #fbbf24, #fb7185)',
            },
          }}
        >
          立即解锁
        </Button>

        <Typography variant="body2" sx={{ color: '#64748b', mt: 0.5 }}>
          沪深300、中证500策略报告免费查看
        </Typography>
      </Box>
    </Box>
  );
}
