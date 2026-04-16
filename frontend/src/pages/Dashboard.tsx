import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Paper, Grid, Button, Card, CardContent,
} from '@mui/material';
import FunctionsIcon from '@mui/icons-material/Functions';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SpeedIcon from '@mui/icons-material/Speed';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { factorApi } from '../api/factors';
import { modelApi } from '../api/models';
import { backtestApi } from '../api/backtests';
import client from '../api/client';

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({ factors: 0, models: 0, backtests: 0, health: 'unknown' });

  useEffect(() => {
    factorApi.list({ limit: 1 }).then((res) => setStats((s) => ({ ...s, factors: res.data.length }))).catch(() => {});
    factorApi.list({ limit: 200 }).then((res) => setStats((s) => ({ ...s, factors: res.data.length }))).catch(() => {});
    modelApi.list({ limit: 200 }).then((res) => setStats((s) => ({ ...s, models: res.data.length }))).catch(() => {});
    backtestApi.list({ limit: 200 }).then((res) => setStats((s) => ({ ...s, backtests: res.data.length }))).catch(() => {});
    client.get('/../health').then((res) => setStats((s) => ({ ...s, health: res.data.status }))).catch(() => {});
  }, []);

  const cards = [
    { title: '因子数量', value: stats.factors, icon: <FunctionsIcon sx={{ fontSize: 40 }} />, color: '#4fc3f7', path: '/factors' },
    { title: '模型数量', value: stats.models, icon: <ModelTrainingIcon sx={{ fontSize: 40 }} />, color: '#f48fb1', path: '/models' },
    { title: '回测数量', value: stats.backtests, icon: <AssessmentIcon sx={{ fontSize: 40 }} />, color: '#66bb6a', path: '/backtests' },
    { title: '系统状态', value: stats.health === 'healthy' ? '正常' : stats.health, icon: <SpeedIcon sx={{ fontSize: 40 }} />, color: stats.health === 'healthy' ? '#66bb6a' : '#ef5350', path: '/performance' },
  ];

  const quickActions = [
    { label: '因子管理', desc: '查看和管理多因子', path: '/factors' },
    { label: '模型管理', desc: '配置模型和因子权重', path: '/models' },
    { label: '择时管理', desc: '查看择时信号', path: '/timing' },
    { label: '组合管理', desc: '生成和查看组合', path: '/portfolios' },
    { label: '回测管理', desc: '运行和查看回测', path: '/backtests' },
    { label: '绩效分析', desc: '查看绩效报告', path: '/performance' },
  ];

  return (
    <Box>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 3 }}>仪表盘</Typography>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        {cards.map((card) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={card.title}>
            <Card sx={{ bgcolor: 'background.paper', cursor: 'pointer' }} onClick={() => navigate(card.path)}>
              <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="body2" color="text.secondary">{card.title}</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: card.color }}>{card.value}</Typography>
                </Box>
                <Box sx={{ color: card.color, opacity: 0.6 }}>{card.icon}</Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Typography variant="h6" sx={{ mb: 2 }}>快捷操作</Typography>
      <Grid container spacing={2}>
        {quickActions.map((action) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={action.label}>
            <Paper
              sx={{ p: 2, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', '&:hover': { bgcolor: 'action.hover' } }}
              onClick={() => navigate(action.path)}
            >
              <Box>
                <Typography sx={{ fontWeight: 600 }}>{action.label}</Typography>
                <Typography variant="body2" color="text.secondary">{action.desc}</Typography>
              </Box>
              <ArrowForwardIcon color="action" />
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
