import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Box,
  TextField,
  Button,
  Typography,
  Link,
  InputAdornment,
  IconButton,
  Alert,
  Divider,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import TaurusBackground from '@/components/background/TaurusBackground';

export default function ResetPassword() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirmPassword) {
      setError(t('auth.passwordMismatch'));
      return;
    }
    setLoading(true);
    try {
      // TODO: call reset password API
      navigate('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('auth.resetFailed'));
    } finally {
      setLoading(false);
    }
  };

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      color: '#e2e8f0',
      borderRadius: 2,
      '& fieldset': { borderColor: 'rgba(100,116,139,0.25)' },
      '&:hover fieldset': { borderColor: 'rgba(100,116,139,0.45)' },
      '&.Mui-focused fieldset': { borderColor: '#6366f1' },
    },
    '& .MuiInputLabel-root': { color: '#64748b' },
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex' }}>
      {/* 左半面：纳斯达克金牛星空 */}
      <Box
        sx={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          display: { xs: 'none', lg: 'flex' },
          flexDirection: 'column',
          justifyContent: 'flex-end',
          p: 6,
        }}
      >
        <TaurusBackground half />
        <Box sx={{ position: 'relative', zIndex: 1 }}>
          <Typography
            variant="h3"
            fontWeight={800}
            sx={{ color: '#f8fafc', letterSpacing: '-0.02em', mb: 1 }}
          >
            Taurus Quant
          </Typography>
          <Typography
            variant="body1"
            sx={{ color: 'rgba(148,163,184,0.8)', maxWidth: 360, lineHeight: 1.7 }}
          >
            {t('auth.brandSubtitle')}
          </Typography>
        </Box>
      </Box>

      {/* 右半面：重置密码表单 */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0b0f1a',
          px: { xs: 3, sm: 6 },
        }}
      >
        <Box sx={{ width: '100%', maxWidth: 400 }}>
          <Box sx={{ display: { xs: 'block', lg: 'none' }, mb: 4 }}>
            <Typography variant="h5" fontWeight={800} sx={{ color: '#f8fafc' }}>
              Taurus Quant
            </Typography>
          </Box>

          <Typography variant="h5" fontWeight={700} sx={{ color: '#f1f5f9', mb: 0.5 }}>
            {t('auth.resetPassword')}
          </Typography>
          <Typography variant="body2" sx={{ color: '#64748b', mb: 4 }}>
            {t('auth.resetPasswordSubtitle')}
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2.5, borderRadius: 2 }}>
              {error}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label={t('auth.newPassword')}
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                      sx={{ color: '#64748b' }}
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              sx={{ mb: 2, ...inputSx }}
            />
            <TextField
              fullWidth
              label={t('auth.confirmPassword')}
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              sx={{ mb: 3, ...inputSx }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={loading}
              sx={{
                py: 1.4,
                borderRadius: 2,
                fontWeight: 600,
                fontSize: '0.95rem',
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                boxShadow: '0 4px 20px rgba(99,102,241,0.3)',
                '&:hover': { background: 'linear-gradient(135deg, #4f46e5, #7c3aed)' },
                '&:disabled': { background: 'rgba(99,102,241,0.4)' },
              }}
            >
              {loading ? t('auth.resetting') : t('auth.resetPassword')}
            </Button>
          </Box>

          <Divider sx={{ my: 3, borderColor: 'rgba(100,116,139,0.15)' }}>
            <Typography variant="caption" sx={{ color: '#475569', px: 1 }}>
              OR
            </Typography>
          </Divider>

          <Box sx={{ textAlign: 'center' }}>
            <Link
              component={RouterLink}
              to="/login"
              sx={{
                color: '#818cf8',
                fontWeight: 500,
                textDecoration: 'none',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              {t('auth.backToLogin')}
            </Link>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
