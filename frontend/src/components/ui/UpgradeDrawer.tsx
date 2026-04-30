import {
  Drawer,
  Box,
  Typography,
  Button,
  IconButton,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

interface UpgradeDrawerProps {
  open: boolean;
  onClose: () => void;
  currentPlan?: string;
  targetPlan?: string;
  targetPrice?: number;
  features?: string[];
}

const UpgradeDrawer: React.FC<UpgradeDrawerProps> = ({
  open,
  onClose,
  currentPlan = '免费版',
  targetPlan = '专业版',
  targetPrice = 299,
  features = [
    '全部股票池',
    '日频调仓',
    '20个模型',
    '50次回测/月',
    'API 接入',
    '深度分析',
    '全格式导出',
  ],
}) => {
  const navigate = useNavigate();

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: 400,
          background: 'rgba(10, 14, 26, 0.95)',
          backdropFilter: 'blur(20px)',
          borderLeft: '1px solid rgba(148, 163, 184, 0.08)',
          boxShadow: '-8px 0 32px rgba(0, 0, 0, 0.5)',
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2.5,
          borderBottom: '1px solid rgba(148, 163, 184, 0.08)',
        }}
      >
        <Typography
          variant="h6"
          sx={{
            fontWeight: 700,
            background: 'linear-gradient(135deg, #22d3ee, #a78bfa)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          升级套餐
        </Typography>
        <IconButton
          onClick={onClose}
          sx={{
            color: 'rgba(148, 163, 184, 0.6)',
            '&:hover': { color: '#22d3ee' },
          }}
        >
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Plan Comparison Flow */}
      <Box sx={{ p: 2.5 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 1.5,
          }}
        >
          {/* Current Plan Box */}
          <Box
            component={motion.div}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            sx={{
              flex: 1,
              p: 2,
              borderRadius: 2,
              background: 'rgba(148, 163, 184, 0.06)',
              border: '1px solid rgba(148, 163, 184, 0.1)',
              textAlign: 'center',
            }}
          >
            <Typography
              variant="caption"
              sx={{ color: 'rgba(148, 163, 184, 0.5)', display: 'block', mb: 0.5 }}
            >
              当前套餐
            </Typography>
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 600, color: 'rgba(148, 163, 184, 0.7)' }}
            >
              {currentPlan}
            </Typography>
          </Box>

          {/* Arrow */}
          <ArrowForwardIcon
            sx={{
              color: 'rgba(148, 163, 184, 0.3)',
              fontSize: 20,
            }}
          />

          {/* Target Plan Box */}
          <Box
            component={motion.div}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            sx={{
              flex: 1,
              p: 2,
              borderRadius: 2,
              background: 'rgba(34, 211, 238, 0.04)',
              border: '1px solid transparent',
              backgroundImage:
                'linear-gradient(rgba(10, 14, 26, 0.95), rgba(10, 14, 26, 0.95)), linear-gradient(135deg, #22d3ee, #a78bfa)',
              backgroundOrigin: 'border-box',
              backgroundClip: 'padding-box, border-box',
              textAlign: 'center',
            }}
          >
            <Typography variant="caption" sx={{ color: '#22d3ee', display: 'block', mb: 0.5 }}>
              目标套餐
            </Typography>
            <Typography
              variant="subtitle1"
              sx={{
                fontWeight: 600,
                background: 'linear-gradient(135deg, #22d3ee, #a78bfa)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              {targetPlan}
            </Typography>
          </Box>
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'rgba(148, 163, 184, 0.06)', mx: 2.5 }} />

      {/* Unlocked Features */}
      <Box sx={{ px: 2.5, pt: 2, pb: 1 }}>
        <Typography
          variant="subtitle2"
          sx={{
            color: 'rgba(148, 163, 184, 0.5)',
            mb: 1,
            textTransform: 'uppercase',
            letterSpacing: 1,
          }}
        >
          解锁功能
        </Typography>
        <List disablePadding>
          {features.map((feature, index) => (
            <ListItem
              key={feature}
              component={motion.div}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: 0.05 * index }}
              sx={{
                px: 0,
                py: 0.75,
              }}
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <CheckCircleIcon
                  sx={{
                    fontSize: 18,
                    color: '#4ade80',
                  }}
                />
              </ListItemIcon>
              <ListItemText
                primary={feature}
                primaryTypographyProps={{
                  variant: 'body2',
                  sx: { color: 'rgba(226, 232, 240, 0.85)' },
                }}
              />
            </ListItem>
          ))}
        </List>
      </Box>

      <Divider sx={{ borderColor: 'rgba(148, 163, 184, 0.06)', mx: 2.5 }} />

      {/* Price Comparison */}
      <Box sx={{ p: 2.5 }}>
        <Typography
          variant="subtitle2"
          sx={{
            color: 'rgba(148, 163, 184, 0.5)',
            mb: 1.5,
            textTransform: 'uppercase',
            letterSpacing: 1,
          }}
        >
          价格对比
        </Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
          }}
        >
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" sx={{ color: 'rgba(148, 163, 184, 0.4)', mb: 0.5 }}>
              {currentPlan}
            </Typography>
            <Typography variant="h6" sx={{ color: 'rgba(148, 163, 184, 0.4)', fontWeight: 600 }}>
              ¥0
              <Typography
                component="span"
                variant="body2"
                sx={{ color: 'rgba(148, 163, 184, 0.3)', ml: 0.25 }}
              >
                /月
              </Typography>
            </Typography>
          </Box>

          <Typography variant="body2" sx={{ color: 'rgba(148, 163, 184, 0.2)' }}>
            →
          </Typography>

          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" sx={{ color: '#22d3ee', mb: 0.5 }}>
              {targetPlan}
            </Typography>
            <Typography
              variant="h5"
              sx={{
                fontWeight: 700,
                color: '#22d3ee',
              }}
            >
              ¥{targetPrice}
              <Typography
                component="span"
                variant="body2"
                sx={{ color: 'rgba(34, 211, 238, 0.5)', ml: 0.25 }}
              >
                /月
              </Typography>
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Action Buttons */}
      <Box sx={{ p: 2.5, mt: 'auto' }}>
        <Button
          fullWidth
          variant="contained"
          size="large"
          component={motion.button}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => {
            onClose();
            navigate('/subscribe');
          }}
          sx={{
            background: 'linear-gradient(135deg, #22d3ee, #a78bfa)',
            color: '#0a0e1a',
            fontWeight: 700,
            fontSize: '1rem',
            py: 1.5,
            borderRadius: 2,
            boxShadow: '0 4px 20px rgba(34, 211, 238, 0.3)',
            '&:hover': {
              background: 'linear-gradient(135deg, #22d3ee, #a78bfa)',
              boxShadow: '0 6px 28px rgba(34, 211, 238, 0.4)',
            },
          }}
        >
          立即升级
        </Button>
        <Button
          fullWidth
          variant="outlined"
          size="large"
          sx={{
            mt: 1.5,
            py: 1.5,
            borderRadius: 2,
            borderColor: 'rgba(148, 163, 184, 0.15)',
            color: 'rgba(148, 163, 184, 0.7)',
            fontWeight: 600,
            '&:hover': {
              borderColor: 'rgba(148, 163, 184, 0.3)',
              background: 'rgba(148, 163, 184, 0.05)',
            },
          }}
        >
          联系销售
        </Button>
      </Box>
    </Drawer>
  );
};

export default UpgradeDrawer;
