import React from 'react';
import { Alert, Typography } from '@mui/material';

interface DisclaimerBannerProps {
  variant?: 'simple' | 'full' | 'page';
  pageType?: 'backtest' | 'portfolio' | 'signal' | 'factor';
  showIcon?: boolean;
}

const DISCLAIMER_TEXT: Record<string, string> = {
  simple: '本平台内容仅供研究与学习使用，不构成任何投资建议。',
  full: '本平台为量化研究与历史分析工具，面向研究、学习与信息展示场景。平台所展示的数据、模型、报告、样本组合及其他内容，均不构成任何形式的投资建议、证券投资咨询意见或收益承诺。历史表现不代表未来结果，用户应基于自身判断独立作出投资决策，并自行承担相应风险。',
  page_backtest: '本回测结果基于历史数据模拟，已考虑T+1、涨跌停等A股交易规则，但实际交易中可能存在滑点、冲击成本、流动性限制等差异。历史回测收益不代表实际交易收益。',
  page_portfolio: '本模拟组合仅供量化研究参考，不构成任何买卖建议。组合持仓和收益数据基于模型计算，与实际投资组合可能存在差异。',
  page_signal: '以下信号由量化模型自动生成，仅供研究参考。模型可能因市场环境变化而失效，请谨慎参考，独立决策。',
  page_factor: '因子IC值和收益率均为历史统计结果，不代表因子未来表现。因子有效性可能随市场环境变化而衰减。',
};

const DisclaimerBanner: React.FC<DisclaimerBannerProps> = ({
  variant = 'simple',
  pageType,
  showIcon = true,
}) => {
  const getText = () => {
    if (variant === 'page' && pageType) {
      return DISCLAIMER_TEXT[`page_${pageType}`] || DISCLAIMER_TEXT.simple;
    }
    return DISCLAIMER_TEXT[variant] || DISCLAIMER_TEXT.simple;
  };

  return (
    <Alert
      severity="warning"
      icon={showIcon ? undefined : false}
      sx={{
        mt: 2,
        mb: 2,
        borderRadius: 1,
        '& .MuiAlert-message': { width: '100%' },
      }}
    >
      <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: 12, lineHeight: 1.6 }}>
        {getText()}
      </Typography>
    </Alert>
  );
};

export default DisclaimerBanner;
