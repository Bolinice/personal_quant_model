import { useState } from 'react';
import { Box, Typography, TextField, Button, Alert, Divider, Snackbar } from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import LockIcon from '@mui/icons-material/Lock';
import LogoutIcon from '@mui/icons-material/Logout';
import CardMembershipIcon from '@mui/icons-material/CardMembership';
import { useAuth } from '@/contexts/AuthContext';
import { authApi } from '@/api';
import { PageHeader, GlassPanel, NeonChip } from '@/components/ui';

export default function Profile() {
  const { user, logout } = useAuth();
  const [username, setUsername] = useState(user?.username || '');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      setSnackbar({ open: true, message: '两次输入的密码不一致', severity: 'error' });
      return;
    }
    if (newPassword.length < 8) {
      setSnackbar({ open: true, message: '密码长度至少8位', severity: 'error' });
      return;
    }

    try {
      await authApi.changePassword({ old_password: oldPassword, new_password: newPassword });
      setSnackbar({ open: true, message: '密码修改成功，请重新登录', severity: 'success' });
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      // 延迟登出让用户看到提示
      setTimeout(() => logout(), 2000);
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.message || '密码修改失败', severity: 'error' });
    }
  };

  return (
    <Box>
      <PageHeader title="个人设置" />

      <Box sx={{ maxWidth: 600 }}>
        {/* 用户信息 */}
        <GlassPanel animate={false} sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #22d3ee 0%, #8b5cf6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontWeight: 700,
                fontSize: '1.5rem',
              }}
            >
              {user?.username?.charAt(0)?.toUpperCase() || 'U'}
            </Box>
            <Box>
              <Typography sx={{ fontWeight: 600, color: '#e2e8f0' }}>{user?.username}</Typography>
              <Typography variant="body2" sx={{ color: '#64748b' }}>
                {user?.email}
              </Typography>
            </Box>
            {user?.is_superuser && <NeonChip label="管理员" size="small" neonColor="amber" />}
          </Box>
          <Divider sx={{ borderColor: 'rgba(148, 163, 184, 0.08)', my: 2 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="body2" sx={{ color: '#64748b' }}>
              注册时间
            </Typography>
            <Typography variant="body2" sx={{ color: '#94a3b8' }}>
              {user?.created_at?.slice(0, 10)}
            </Typography>
          </Box>
        </GlassPanel>

        {/* 修改密码 */}
        <GlassPanel animate={false} sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <LockIcon sx={{ color: '#22d3ee', fontSize: 20 }} />
            <Typography sx={{ fontWeight: 600 }}>修改密码</Typography>
          </Box>

          <TextField
            fullWidth
            label="当前密码"
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            sx={{ mb: 2 }}
            slotProps={{ input: { sx: { borderRadius: 2 } } }}
          />
          <TextField
            fullWidth
            label="新密码"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            sx={{ mb: 2 }}
            slotProps={{ input: { sx: { borderRadius: 2 } } }}
          />
          <TextField
            fullWidth
            label="确认新密码"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            sx={{ mb: 2 }}
            slotProps={{ input: { sx: { borderRadius: 2 } } }}
          />

          <Button
            variant="contained"
            onClick={handleChangePassword}
            disabled={!oldPassword || !newPassword || !confirmPassword}
            sx={{
              borderRadius: 2,
              background: 'linear-gradient(135deg, #22d3ee 0%, #8b5cf6 100%)',
              '&:hover': { opacity: 0.9 },
            }}
          >
            修改密码
          </Button>
        </GlassPanel>

        {/* 退出登录 */}
        <GlassPanel animate={false}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <LogoutIcon sx={{ color: '#f43f5e', fontSize: 20 }} />
              <Typography sx={{ fontWeight: 600 }}>退出登录</Typography>
            </Box>
            <Button variant="outlined" color="error" onClick={logout} sx={{ borderRadius: 2 }}>
              退出
            </Button>
          </Box>
        </GlassPanel>
      </Box>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
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
