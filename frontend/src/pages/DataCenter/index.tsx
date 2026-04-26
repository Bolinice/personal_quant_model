import { Box, Typography } from '@mui/material';
import { PageHeader, GlassPanel } from '@/components/ui';
import DisclaimerBanner from '@/components/compliance/DisclaimerBanner';

export default function DataCenter() {
  return (
    <Box>
      <PageHeader title="数据中心" />
      <GlassPanel sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>市场数据概览</Typography>
        <Typography sx={{ color: '#64748b' }}>请通过后端脚本同步数据后查看</Typography>
      </GlassPanel>
      <GlassPanel sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>数据源状态</Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography sx={{ color: '#94a3b8' }}>主数据源 (AKShare)</Typography>
            <Typography sx={{ color: '#10b981', fontSize: '0.85rem' }}>在线</Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography sx={{ color: '#94a3b8' }}>备数据源 (Tushare)</Typography>
            <Typography sx={{ color: '#64748b', fontSize: '0.85rem' }}>未配置</Typography>
          </Box>
        </Box>
      </GlassPanel>
      <DisclaimerBanner variant="simple" />
    </Box>
  );
}
