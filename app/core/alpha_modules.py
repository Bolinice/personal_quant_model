"""
Alpha模块化架构
实现GPT设计7.1-7.4节: 不同收益来源分模块建模
- PriceAlphaModule: 价格行为Alpha (5-10日行业中性超额)
- FundamentalAlphaModule: 价值质量Alpha (10-20日超额)
- RevisionAlphaModule: 预期修正Alpha (5-20日超额)
- FlowEventAlphaModule: 资金流/事件Alpha (3-10日超额)

每个模块: 独立打分、独立监控、独立训练
第一版: 线性加权(IC加权或等权)
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logging import logger


class AlphaModule(ABC):
    """Alpha模块基类 - 统一接口"""

    name: str = ""
    description: str = ""
    prediction_horizon: int = 10
    factors: List[str] = []

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: 因子权重字典 {factor_name: weight}, None=等权
        """
        self._weights = weights or {}
        self._ic_cache: Dict[str, pd.Series] = {}

    @abstractmethod
    def score(self, factor_df: pd.DataFrame) -> pd.Series:
        """
        计算模块alpha分数

        Args:
            factor_df: 因子数据, index=(ts_code, trade_date)或ts_code,
                       columns包含该模块的因子

        Returns:
            模块分数, 同factor_df的index
        """

    def diagnostics(self, factor_df: pd.DataFrame,
                    forward_returns: Optional[pd.Series] = None,
                    window: int = 60) -> Dict:
        """
        模块诊断: IC/IR/decay/coverage

        Args:
            factor_df: 因子数据
            forward_returns: 未来收益 (可选, 用于计算IC)
            window: 滚动窗口

        Returns:
            诊断结果字典
        """
        result = {
            'module': self.name,
            'n_factors': len(self.factors),
            'factors': self.factors,
            'prediction_horizon': self.prediction_horizon,
        }

        # 因子覆盖率
        available = [f for f in self.factors if f in factor_df.columns]
        result['coverage'] = len(available) / len(self.factors) if self.factors else 0
        result['available_factors'] = available
        result['missing_factors'] = [f for f in self.factors if f not in factor_df.columns]

        # IC统计 (如果提供了forward_returns)
        if forward_returns is not None and not forward_returns.empty:
            ic_stats = {}
            for factor_name in available:
                factor_vals = factor_df[factor_name]
                if isinstance(factor_df.index, pd.MultiIndex):
                    # (ts_code, trade_date) index
                    aligned = pd.DataFrame({
                        'factor': factor_vals,
                        'return': forward_returns
                    }).dropna()
                    if len(aligned) > 30:
                        # 按日期计算截面IC
                        ic_series = aligned.groupby(level=1 if aligned.index.nlevels > 1 else 0).apply(
                            lambda x: x['factor'].corr(x['return'], method='spearman')
                        )
                        ic_stats[factor_name] = {
                            'mean_ic': float(ic_series.mean()),
                            'ir': float(ic_series.mean() / ic_vals.std()) if (ic_vals := ic_series.dropna()).std() > 0 else 0,
                            'ic_ir': float(ic_series.mean() / ic_series.std()) if ic_series.std() > 0 else 0,
                            'win_rate': float((ic_series > 0).mean()),
                        }
            result['ic_stats'] = ic_stats

        return result

    def _compute_weighted_score(self, factor_df: pd.DataFrame) -> pd.Series:
        """
        加权计算模块分数

        1. 每个因子横截面标准化(z-score)
        2. 按权重加权求和
        3. 结果再标准化
        """
        available = [f for f in self.factors if f in factor_df.columns]
        if not available:
            logger.warning(f"Module {self.name}: no available factors")
            return pd.Series(0.0, index=factor_df.index)

        # 标准化每个因子
        standardized = pd.DataFrame(index=factor_df.index)
        for f in available:
            vals = factor_df[f].copy()
            # 横截面标准化: 按日期分组z-score
            if isinstance(factor_df.index, pd.MultiIndex) and factor_df.index.nlevels >= 2:
                # index level 1 = trade_date
                standardized[f] = vals.groupby(level=1).apply(
                    lambda x: (x - x.mean()) / x.std() if x.std() > 0 else x * 0
                )
            else:
                standardized[f] = (vals - vals.mean()) / vals.std() if vals.std() > 0 else vals * 0

        # 权重
        if self._weights:
            w = {f: self._weights.get(f, 0) for f in available}
            total_w = sum(w.values())
            if total_w == 0:
                w = {f: 1.0 / len(available) for f in available}
            else:
                w = {f: v / total_w for f, v in w.items()}
        else:
            w = {f: 1.0 / len(available) for f in available}

        # 加权求和
        score = pd.Series(0.0, index=factor_df.index)
        for f in available:
            score += standardized[f] * w[f]

        # 结果标准化
        if isinstance(factor_df.index, pd.MultiIndex) and factor_df.index.nlevels >= 2:
            score = score.groupby(level=1).apply(
                lambda x: (x - x.mean()) / x.std() if x.std() > 0 else x * 0
            )
        else:
            score = (score - score.mean()) / score.std() if score.std() > 0 else score * 0

        return score


class PriceAlphaModule(AlphaModule):
    """
    价格行为Alpha模块 (GPT设计7.1节)
    预测周期: 5-10日行业中性超额
    核心逻辑: 动量/反转/波动率/技术形态
    """
    name = "price"
    description = "价格行为Alpha: 动量/反转/波动率/技术形态"
    prediction_horizon = 5
    factors = [
        # 反转因子
        'ret_1m_reversal',      # 1月反转
        'ret_3m_skip1',         # 3月动量(跳过近1月)
        'ret_6m_skip1',         # 6月动量(跳过近1月)
        'ret_12m_skip1',        # 12月动量(跳过近1月)
        # 波动率因子
        'vol_20d',              # 20日波动率
        'vol_60d',              # 60日波动率
        # 技术因子
        'rsi_14d',              # RSI
        'bollinger_position',   # 布林带位置
        'macd_signal',          # MACD信号
        # 日内/隔夜
        'overnight_return',     # 隔夜收益
        'intraday_return_ratio', # 日内收益占比
        'vpin',                 # VPIN
    ]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        # GPT设计建议: 反转在A股最重要
        default_weights = {
            'ret_1m_reversal': 0.20,
            'ret_3m_skip1': 0.10,
            'ret_6m_skip1': 0.10,
            'ret_12m_skip1': 0.05,
            'vol_20d': 0.10,
            'vol_60d': 0.05,
            'rsi_14d': 0.10,
            'bollinger_position': 0.08,
            'macd_signal': 0.07,
            'overnight_return': 0.08,
            'intraday_return_ratio': 0.05,
            'vpin': 0.02,
        }
        if weights:
            default_weights.update(weights)
        super().__init__(weights=default_weights)

    def score(self, factor_df: pd.DataFrame) -> pd.Series:
        return self._compute_weighted_score(factor_df)


class FundamentalAlphaModule(AlphaModule):
    """
    价值质量Alpha模块 (GPT设计7.2节)
    预测周期: 10-20日超额
    核心逻辑: 价值/质量/应计异常
    """
    name = "fundamental"
    description = "价值质量Alpha: 价值/质量/应计异常"
    prediction_horizon = 10
    factors = [
        # 价值因子
        'ep_ttm',               # E/P (TTM)
        'bp',                   # B/P
        'sp_ttm',               # S/P (TTM)
        'cfp_ttm',              # CF/P (TTM)
        # 质量因子
        'roe',                  # ROE
        'roa',                  # ROA
        'gross_profit_margin',  # 毛利率
        # 应计异常
        'sloan_accrual',        # Sloan应计
        'cfo_to_net_profit',    # 经营现金流/净利润
        'earnings_stability',   # 盈利稳定性
        'accrual_anomaly',      # 应计异常
    ]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        default_weights = {
            'ep_ttm': 0.15,
            'bp': 0.15,
            'sp_ttm': 0.08,
            'cfp_ttm': 0.10,
            'roe': 0.12,
            'roa': 0.08,
            'gross_profit_margin': 0.08,
            'sloan_accrual': 0.08,
            'cfo_to_net_profit': 0.06,
            'earnings_stability': 0.05,
            'accrual_anomaly': 0.05,
        }
        if weights:
            default_weights.update(weights)
        super().__init__(weights=default_weights)

    def score(self, factor_df: pd.DataFrame) -> pd.Series:
        return self._compute_weighted_score(factor_df)


class RevisionAlphaModule(AlphaModule):
    """
    预期修正Alpha模块 (GPT设计7.3节)
    预测周期: 5-20日超额
    核心逻辑: 分析师修正/SUE/盈利惊喜
    """
    name = "revision"
    description = "预期修正Alpha: 分析师修正/SUE/盈利惊喜"
    prediction_horizon = 10
    factors = [
        'sue',                  # 标准化未预期盈利
        'analyst_revision_1m',  # 分析师1月修正
        'analyst_coverage',     # 分析师覆盖度
        'earnings_surprise',    # 盈利惊喜
    ]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        default_weights = {
            'sue': 0.30,
            'analyst_revision_1m': 0.30,
            'analyst_coverage': 0.15,
            'earnings_surprise': 0.25,
        }
        if weights:
            default_weights.update(weights)
        super().__init__(weights=default_weights)

    def score(self, factor_df: pd.DataFrame) -> pd.Series:
        return self._compute_weighted_score(factor_df)


class FlowEventAlphaModule(AlphaModule):
    """
    资金流/事件Alpha模块 (GPT设计7.4节)
    预测周期: 3-10日超额
    核心逻辑: 北向/聪明钱/融资融券/大单/流动性
    """
    name = "flow_event"
    description = "资金流/事件Alpha: 北向/聪明钱/融资融券/大单/流动性"
    prediction_horizon = 5
    factors = [
        'north_net_buy_ratio',  # 北向净买入占比
        'smart_money_ratio',    # 聪明钱占比
        'margin_signal',        # 融资融券信号
        'large_order_ratio',    # 大单占比
        'turnover_20d',         # 20日换手率
        'amihud_20d',           # Amihud非流动性
    ]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        default_weights = {
            'north_net_buy_ratio': 0.25,
            'smart_money_ratio': 0.20,
            'margin_signal': 0.15,
            'large_order_ratio': 0.15,
            'turnover_20d': 0.15,
            'amihud_20d': 0.10,
        }
        if weights:
            default_weights.update(weights)
        super().__init__(weights=default_weights)

    def score(self, factor_df: pd.DataFrame) -> pd.Series:
        return self._compute_weighted_score(factor_df)


# ==================== 模块注册 ====================

MODULE_REGISTRY: Dict[str, type] = {
    'price': PriceAlphaModule,
    'fundamental': FundamentalAlphaModule,
    'revision': RevisionAlphaModule,
    'flow_event': FlowEventAlphaModule,
}


def get_module(name: str, **kwargs) -> AlphaModule:
    """获取Alpha模块实例"""
    if name not in MODULE_REGISTRY:
        raise ValueError(f"Unknown module: {name}, available: {list(MODULE_REGISTRY.keys())}")
    return MODULE_REGISTRY[name](**kwargs)


def get_all_modules(**kwargs) -> List[AlphaModule]:
    """获取所有Alpha模块实例"""
    return [cls(**kwargs) for cls in MODULE_REGISTRY.values()]