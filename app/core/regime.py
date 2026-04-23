"""
市场状态(Regime)检测模块
实现GPT设计7.5节: Regime模块不预测个股收益，而是判断当前市场环境适合哪类alpha
检测: trending(趋势市)/mean_reverting(震荡市)/defensive(防御市)/risk_on(进攻市)
用途: 给各alpha模块动态调权、调整组合风险参数
"""
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.logging import logger


# Regime类型定义
REGIME_TRENDING = 'trending'         # 趋势市: 价格行为/修正权重更高
REGIME_MEAN_REVERTING = 'mean_reverting'  # 震荡市: 反转/价值权重更高
REGIME_DEFENSIVE = 'defensive'       # 防御市: 质量/低波动权重更高
REGIME_RISK_ON = 'risk_on'           # 进攻市: 资金/事件权重更高

# Regime对应的模块权重调整 (GPT设计9.3节)
REGIME_WEIGHT_ADJUSTMENTS = {
    REGIME_TRENDING: {
        'price': 1.2,        # 趋势市: 价格行为更有效
        'fundamental': 0.9,
        'revision': 1.1,     # 趋势市: 修正信号更有效
        'flow_event': 1.0,
    },
    REGIME_MEAN_REVERTING: {
        'price': 1.0,
        'fundamental': 1.2,  # 震荡市: 价值更有效
        'revision': 0.9,
        'flow_event': 0.9,
    },
    REGIME_DEFENSIVE: {
        'price': 0.8,        # 防御市: 降低价格行为权重
        'fundamental': 1.3,  # 质量/价值更有效
        'revision': 0.9,
        'flow_event': 0.7,
    },
    REGIME_RISK_ON: {
        'price': 1.0,
        'fundamental': 0.8,
        'revision': 1.0,
        'flow_event': 1.3,   # 进攻市: 资金/事件更有效
    },
}


class RegimeDetector:
    """市场状态检测器 - GPT设计7.5节"""

    def __init__(self):
        pass

    # ==================== 市场状态特征 ====================

    def market_features(self, market_data: pd.DataFrame,
                         date_col: str = 'trade_date',
                         price_col: str = 'close',
                         volume_col: str = 'volume',
                         amount_col: str = 'amount') -> Dict[str, float]:
        """
        计算市场状态特征 (GPT设计5.6节 + 7.5节)

        Args:
            market_data: 指数行情, 需含 trade_date/close/volume/amount
                         也可含个股行情(用于计算breadth等)

        Returns:
            市场状态特征字典
        """
        if market_data.empty or price_col not in market_data.columns:
            return {}

        df = market_data.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.sort_values(date_col)

        features = {}

        # 1. 市场趋势: 均线斜率 (20日/60日)
        close = df[price_col].values
        if len(close) >= 60:
            ma20 = np.mean(close[-20:])
            ma60 = np.mean(close[-60:])
            features['market_trend_20d'] = (ma20 - close[-1]) / close[-1] if close[-1] > 0 else 0
            features['market_trend_60d'] = (ma60 - close[-1]) / close[-1] if close[-1] > 0 else 0
            # MA20 vs MA60 交叉
            features['ma_cross'] = (ma20 - ma60) / ma60 if ma60 > 0 else 0
        elif len(close) >= 20:
            ma20 = np.mean(close[-20:])
            features['market_trend_20d'] = (ma20 - close[-1]) / close[-1] if close[-1] > 0 else 0

        # 2. 市场波动率
        returns = df[price_col].pct_change().dropna()
        if len(returns) >= 20:
            features['market_vol_20d'] = returns.tail(20).std() * np.sqrt(252)
            features['market_vol_60d'] = returns.tail(60).std() * np.sqrt(252) if len(returns) >= 60 else features['market_vol_20d']
            # 波动率变化
            vol_short = returns.tail(10).std()
            vol_long = returns.tail(60).std() if len(returns) >= 60 else returns.tail(20).std()
            features['vol_ratio'] = vol_short / vol_long if vol_long > 0 else 1.0

        # 3. 市场宽度 (上涨股票占比) - 需要个股数据
        if 'pct_chg' in df.columns and 'ts_code' in df.columns:
            # 如果是个股数据, 计算breadth
            latest = df[df[date_col] == df[date_col].max()]
            if not latest.empty and 'pct_chg' in latest.columns:
                pct_chg = latest['pct_chg'].dropna()
                features['breadth'] = (pct_chg > 0).mean() if len(pct_chg) > 0 else 0.5

        # 4. 市场收益
        if len(close) >= 2:
            features['market_return_1d'] = close[-1] / close[-2] - 1
        if len(close) >= 20:
            features['market_return_20d'] = close[-1] / close[-20] - 1
        if len(close) >= 60:
            features['market_return_60d'] = close[-1] / close[-60] - 1

        return features

    def size_value_spread(self, large_cap_df: pd.DataFrame,
                           small_cap_df: pd.DataFrame,
                           date_col: str = 'trade_date',
                           price_col: str = 'close',
                           window: int = 20) -> float:
        """
        大小盘收益差 (GPT设计5.6节)

        Args:
            large_cap_df: 大盘指数行情
            small_cap_df: 小盘指数行情
            window: 计算窗口

        Returns:
            大小盘收益差 (正值=小盘更强)
        """
        if large_cap_df.empty or small_cap_df.empty:
            return 0.0

        large_ret = large_cap_df[price_col].pct_change().tail(window).mean()
        small_ret = small_cap_df[price_col].pct_change().tail(window).mean()

        return small_ret - large_ret

    def sector_dispersion(self, sector_returns: pd.DataFrame,
                          date_col: str = 'trade_date',
                          return_col: str = 'return') -> float:
        """
        行业离散度 (GPT设计5.6节)
        行业收益的离散程度，高离散度意味着行业轮动机会多

        Args:
            sector_returns: 行业收益 DataFrame, 需含 industry/return 列

        Returns:
            行业收益标准差
        """
        if sector_returns.empty or return_col not in sector_returns.columns:
            return 0.0

        returns = sector_returns[return_col].dropna()
        if len(returns) < 3:
            return 0.0

        return returns.std()

    # ==================== Regime检测 ====================

    def detect(self, market_data: pd.DataFrame,
               large_cap_df: pd.DataFrame = None,
               small_cap_df: pd.DataFrame = None,
               sector_returns: pd.DataFrame = None) -> str:
        """
        检测当前市场regime

        基于多维度特征综合判断:
        - 趋势强度 + 方向 → trending/mean_reverting
        - 波动率 + 宽度 → defensive/risk_on
        - 大小盘差 → 风格偏好

        Args:
            market_data: 指数行情(如沪深300)
            large_cap_df: 大盘指数(可选)
            small_cap_df: 小盘指数(可选)
            sector_returns: 行业收益(可选)

        Returns:
            regime标签: trending/mean_reverting/defensive/risk_on
        """
        features = self.market_features(market_data)

        if not features:
            return REGIME_MEAN_REVERTING  # 默认震荡市

        # 综合评分
        trend_score = 0.0
        vol_score = 0.0
        breadth_score = 0.5

        # 趋势评分
        trend_20d = features.get('market_trend_20d', 0)
        trend_60d = features.get('market_trend_60d', 0)
        ma_cross = features.get('ma_cross', 0)

        # 强趋势: 20d和60d方向一致且幅度大
        if abs(trend_20d) > 0.03 and abs(trend_60d) > 0.05:
            trend_score = np.sign(trend_20d) * min(abs(trend_20d) * 10, 1.0)
        elif abs(ma_cross) > 0.02:
            trend_score = np.sign(ma_cross) * min(abs(ma_cross) * 5, 0.5)
        else:
            trend_score = 0.0  # 震荡

        # 波动率评分
        vol_20d = features.get('market_vol_20d', 0.2)
        vol_ratio = features.get('vol_ratio', 1.0)

        if vol_20d > 0.30 or vol_ratio > 1.5:
            vol_score = -1.0  # 高波动 → 防御
        elif vol_20d < 0.15 and vol_ratio < 0.7:
            vol_score = 1.0   # 低波动 → 进攻
        else:
            vol_score = 0.0

        # 宽度评分
        breadth = features.get('breadth', 0.5)
        if breadth > 0.6:
            breadth_score = 1.0  # 多头宽度
        elif breadth < 0.4:
            breadth_score = -1.0  # 空头宽度
        else:
            breadth_score = 0.0

        # 大小盘差
        size_spread = 0.0
        if large_cap_df is not None and small_cap_df is not None:
            size_spread = self.size_value_spread(large_cap_df, small_cap_df)

        # 综合判断
        # 趋势市: 强趋势 + 正方向 + 宽度好
        # 震荡市: 无趋势 + 波动率适中
        # 防御市: 高波动 + 宽度差 + 负趋势
        # 进攻市: 低波动 + 宽度好 + 正趋势 + 小盘强

        composite = trend_score + vol_score + breadth_score

        if composite >= 1.5 and trend_score > 0:
            regime = REGIME_RISK_ON
        elif composite >= 0.5 and abs(trend_score) > 0.3:
            regime = REGIME_TRENDING
        elif composite <= -1.0:
            regime = REGIME_DEFENSIVE
        else:
            regime = REGIME_MEAN_REVERTING

        logger.info(
            "Regime detected",
            extra={
                "regime": regime,
                "trend_score": round(trend_score, 3),
                "vol_score": round(vol_score, 3),
                "breadth_score": round(breadth_score, 3),
                "composite": round(composite, 3),
                "vol_20d": round(vol_20d, 4),
                "size_spread": round(size_spread, 4),
            },
        )

        return regime

    def get_weight_adjustments(self, regime: str,
                                base_weights: Dict[str, float]) -> Dict[str, float]:
        """
        根据regime调整模块权重 (GPT设计9.3节)

        Args:
            regime: 当前市场状态
            base_weights: 基础模块权重 {module_name: weight}

        Returns:
            调整后的权重
        """
        adjustments = REGIME_WEIGHT_ADJUSTMENTS.get(regime, {})

        adjusted = {}
        for module, weight in base_weights.items():
            adj_factor = adjustments.get(module, 1.0)
            adjusted[module] = weight * adj_factor

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def detect_with_confidence(self, market_data: pd.DataFrame,
                                large_cap_df: pd.DataFrame = None,
                                small_cap_df: pd.DataFrame = None) -> Dict[str, Any]:
        """
        检测regime并返回置信度

        Returns:
            {regime: str, confidence: float, features: Dict, weight_adjustments: Dict}
        """
        regime = self.detect(market_data, large_cap_df, small_cap_df)
        features = self.market_features(market_data)

        # 简单置信度: 基于特征的一致性
        trend_20d = abs(features.get('market_trend_20d', 0))
        vol_ratio = features.get('vol_ratio', 1.0)
        breadth = features.get('breadth', 0.5)

        # 特征越偏离中性，置信度越高
        confidence = min(
            (trend_20d * 10 + abs(vol_ratio - 1.0) * 2 + abs(breadth - 0.5) * 2) / 3,
            1.0
        )
        confidence = max(confidence, 0.3)  # 最低30%置信度

        base_weights = {'price': 0.30, 'fundamental': 0.25, 'revision': 0.25, 'flow_event': 0.20}
        adjusted_weights = self.get_weight_adjustments(regime, base_weights)

        return {
            'regime': regime,
            'confidence': round(confidence, 3),
            'features': features,
            'weight_adjustments': adjusted_weights,
        }