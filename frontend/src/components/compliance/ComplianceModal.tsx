import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Checkbox,
  FormControlLabel,
  Button,
  Box,
} from '@mui/material';

interface ComplianceModalProps {
  autoShow?: boolean;
  storageKey?: string;
  open?: boolean;
  onClose?: () => void;
  onConfirm?: () => void;
}

const COMPLIANCE_POINTS = [
  '本平台为量化策略研究工具，不提供投资建议',
  '所有策略回测结果均为历史数据，不代表未来收益',
  '投资有风险，您应基于独立判断做出投资决策',
];

const ComplianceModal: React.FC<ComplianceModalProps> = ({
  autoShow = true,
  storageKey = 'compliance_acknowledged',
  open: controlledOpen,
  onClose,
  onConfirm,
}) => {
  const [acknowledged, setAcknowledged] = useState(false);

  // Initialize visibility based on localStorage
  const getInitialVisibility = () => {
    if (controlledOpen !== undefined) return false;
    if (!autoShow) return false;
    return !localStorage.getItem(storageKey);
  };

  const [internalVisible, setInternalVisible] = useState(getInitialVisibility);

  const visible = controlledOpen !== undefined ? controlledOpen : internalVisible;

  const handleConfirm = () => {
    localStorage.setItem(storageKey, new Date().toISOString());
    setInternalVisible(false);
    onConfirm?.();
    onClose?.();
  };

  const handleCancel = () => {
    setInternalVisible(false);
    onClose?.();
  };

  return (
    <Dialog
      open={visible}
      onClose={controlledOpen !== undefined ? handleCancel : undefined}
      slotProps={{
        backdrop: {
          onClick: controlledOpen === undefined ? undefined : handleCancel,
        },
      }}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle sx={{ fontWeight: 700 }}>欢迎使用A股多因子增强策略平台</DialogTitle>
      <DialogContent>
        <Typography sx={{ mb: 2 }}>在使用本平台前，请您知悉：</Typography>
        {COMPLIANCE_POINTS.map((point, idx) => (
          <Box key={idx} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1, pl: 2 }}>
            <Typography sx={{ color: 'warning.main', fontSize: 14 }}>⚠</Typography>
            <Typography variant="body2">{point}</Typography>
          </Box>
        ))}
        <Box sx={{ mt: 2 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                size="small"
              />
            }
            label={
              <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: 12 }}>
                我已阅读并了解以上内容
              </Typography>
            }
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={!acknowledged}
          fullWidth
          sx={{
            py: 1.2,
            borderRadius: 2,
            fontWeight: 700,
            background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
            '&:hover': { background: 'linear-gradient(135deg, #06b6d4, #7c3aed)' },
          }}
        >
          我已了解，继续使用
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ComplianceModal;
