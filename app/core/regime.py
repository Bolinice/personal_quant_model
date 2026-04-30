"""
市场状态(Regime)检测模块
实现GPT设计7.5节: Regime模块不预测个股收益，而是判断当前市场环境适合哪类alpha
检测: trending(趋势市)/mean_reverting(震荡市)/defensive(防御市)/risk_on(进攻市)
用途: 给各alpha模块动态调权、调整组合风险参数
"""

from typing import Any

import numpy as np
import pandas as pd

from app.core.logging import logger

# Regime类型定义
REGIME_TRENDING = "trending"  # 趋势市: 价格行为/修正权重更高
REGIME_MEAN_REVERTING = "mean_reverting"  # 震荡市: 反转/价值权重更高
REGIME_DEFENSIVE = "defensive"  # 防御市: 质量/低波动权重更高
REGIME_RISK_ON = "risk_on"  # 进攻市: 资金/事件权重更高

# Regime对应的模块权重调整 (V2: 与EnsembleEngine一致, 使用增量而非乘数)
# 增量调整而非乘数: 乘数在边界处行为不稳定(如权重接近0时乘数效果异常)
REGIME_WEIGHT_ADJUSTMENTS = {
    REGIME_RISK_ON: {
        "quality_growth": -0.05,  # 进攻: 质量↓ — 牛市中质量因子alpha衰减, 成长股更受追捧
        "expectation": 0.00,
        "residual_momentum": +0.08,  # 动量↑ — 进攻市趋势延续性强, 动量因子IC上升
        "flow_confirm": +0.05,  # 资金流↑ — 资金涌入是进攻市的核心确认信号
    },
    REGIME_TRENDING: {
        # 趨势: 均衡 — 趋势市无极端偏好, 保持基线权重
        "quality_growth": 0.00,
        "expectation": 0.00,
        "residual_momentum": 0.00,
        "flow_confirm": 0.00,
    },
    REGIME_DEFENSIVE: {
        "quality_growth": +0.08,  # 防御: 质量↑ — 防御市资金回流确定性高的质量股
        "expectation": +0.02,
        "residual_momentum": -0.08,  # 动量↓ — 防御市动量反转频繁, 趋势不可靠
        "flow_confirm": -0.02,
    },
    REGIME_MEAN_REVERTING: {
        "quality_growth": +0.02,
        "expectation": +0.06,  # 震荡: 修正↑ — 震荡市中分析师修正信号更具区分度
        "residual_momentum": -0.06,  # 动量↓ — 震荡市动量因子衰减甚至反转
        "flow_confirm": -0.02,
    },
}


class RegimeDetector:
    """市场状态检测器 - GPT设计7.5节"""

    # 迟滞阈值: 避免波动率在阈值附近反复切换状态(抖动)
    # 进入防御阈值低于退出防御阈值, 进入进攻阈值高于退出进攻阈值
    VOL_HIGH_ENTER = 0.30  # 进入防御: 年化波动率>30%
    VOL_HIGH_EXIT = 0.25  # 退出防御: 年化波动率<25%
    VOL_LOW_ENTER = 0.15  # 进入进攻: 年化波动率<15%
    VOL_LOW_EXIT = 0.20  # 退出进攻: 年化波动率>20%
    VOL_RATIO_HIGH_ENTER = 1.5  # 波动率比>1.5进入防御
    VOL_RATIO_HIGH_EXIT = 1.3  # 波动率比<1.3退出防御
    VOL_RATIO_LOW_ENTER = 0.7  # 波动率比<0.7进入进攻
    VOL_RATIO_LOW_EXIT = 0.9  # 波动率比>0.9退出进攻

    def __init__(self):
        self._prev_vol_score = 0.0  # 迟滞状态: 记住上一次的波动率评分

    # ==================== 市场状态特征 ====================

    def market_features(
        self,
        market_data: pd.DataFrame,
        date_col: str = "trade_date",
        price_col: str = "close",
        volume_col: str = "volume",
        amount_col: str = "amount",
    ) -> dict[str, float]:
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
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.sort_values(date_col)

        features = {}

        # 1. 市场趋势: 均线斜率 (20日/60日)
        # 均线斜率而非价格变化: 斜率衡量趋势持续性, 单日涨跌幅噪声大
        close = df[price_col].values
        if len(close) >= 60:
            ma20 = np.mean(close[-20:])
            ma60 = np.mean(close[-60:])
            # (close - MA) / close: 正值=上升趋势(close>MA), 负值=下降趋势
            # 原公式 (MA - close)/close 符号反转, 修正后与直觉一致: 正=涨, 负=跌
            features["market_trend_20d"] = (close[-1] - ma20) / close[-1] if close[-1] > 0 else 0
            features["market_trend_60d"] = (close[-1] - ma60) / close[-1] if close[-1] > 0 else 0
            # MA20 vs MA60 交叉: 正值=金叉(MA20>MA60), 负值=死叉
            features["ma_cross"] = (ma20 - ma60) / ma60 if ma60 > 0 else 0
        elif len(close) >= 20:
            ma20 = np.mean(close[-20:])
            features["market_trend_20d"] = (close[-1] - ma20) / close[-1] if close[-1] > 0 else 0

        # 2. 市场波动率
        # 年化波动率: 日std * sqrt(252), A股年均约252个交易日
        returns = df[price_col].pct_change().dropna()
        if len(returns) >= 20:
            features["market_vol_20d"] = returns.tail(20).std() * np.sqrt(252)
            features["market_vol_60d"] = (
                returns.tail(60).std() * np.sqrt(252) if len(returns) >= 60 else features["market_vol_20d"]
            )
            # 波动率变化
            vol_short = returns.tail(10).std()
            vol_long = returns.tail(60).std() if len(returns) >= 60 else returns.tail(20).std()
            features["vol_ratio"] = vol_short / vol_long if vol_long > 0 else 1.0

        # 3. 市场宽度 (上涨股票占比) - 需要个股数据
        # 宽度>0.6=普涨(多头), <0.4=普跌(空头), 中间=分化 — 区分"指数涨个股跌"的虚假趋势
        if "pct_chg" in df.columns and "ts_code" in df.columns:
            # 如果是个股数据, 计算breadth
            latest = df[df[date_col] == df[date_col].max()]
            if not latest.empty and "pct_chg" in latest.columns:
                pct_chg = latest["pct_chg"].dropna()
                features["breadth"] = (pct_chg > 0).mean() if len(pct_chg) > 0 else 0.5

        # 4. 市场收益
        if len(close) >= 2:
            features["market_return_1d"] = close[-1] / close[-2] - 1
        if len(close) >= 20:
            features["market_return_20d"] = close[-1] / close[-20] - 1
        if len(close) >= 60:
            features["market_return_60d"] = close[-1] / close[-60] - 1

        return features

    def size_value_spread(
        self,
        large_cap_df: pd.DataFrame,
        small_cap_df: pd.DataFrame,
        date_col: str = "trade_date",
        price_col: str = "close",
        window: int = 20,
    ) -> float:
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

    def sector_dispersion(
        self, sector_returns: pd.DataFrame, date_col: str = "trade_date", return_col: str = "return"
    ) -> float:
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

    def detect(
        self,
        market_data: pd.DataFrame,
        large_cap_df: pd.DataFrame = None,
        small_cap_df: pd.DataFrame = None,
        sector_returns: pd.DataFrame = None,
    ) -> tuple[str, float]:
        """
        检测当前市场regime并返回置信度

        Returns:
            (regime标签, 置信度): 如 ("trending", 0.7)
        """
        features = self.market_features(market_data)

        if not features:
            return REGIME_MEAN_REVERTING, 0.3  # 默认震荡市 — 无数据时保守选择, 震荡权重最均衡

        # 综合评分
        trend_score = 0.0
        vol_score = 0.0
        breadth_score = 0.5

        # 趋势评分
        trend_20d = features.get("market_trend_20d", 0)
        trend_60d = features.get("market_trend_60d", 0)
        ma_cross = features.get("ma_cross", 0)

        # 强趋势: 20d和60d方向一致且幅度大
        # 阈值3%/5%: A股指数日均波动约1-2%, 3%以上斜率意味着持续性趋势
        # market_trend_20d = (close - MA20)/close: 正值=上升趋势
        trend_20d_adj = trend_20d
        trend_60d_adj = trend_60d
        if abs(trend_20d_adj) > 0.03 and abs(trend_60d_adj) > 0.05:
            trend_score = np.sign(trend_20d_adj) * min(abs(trend_20d_adj) * 10, 1.0)
        elif abs(ma_cross) > 0.02:
            trend_score = np.sign(ma_cross) * min(abs(ma_cross) * 5, 0.5)
        else:
            trend_score = 0.0  # 震荡

        # 波动率评分 (带迟滞: 防止阈值附近状态抖动)
        # 状态机设计: 进入阈值 != 退出阈值, 形成迟滞区间避免抖动
        vol_20d = features.get("market_vol_20d", 0.2)
        vol_ratio = features.get("vol_ratio", 1.0)

        # 状态机逻辑: 根据当前状态(_prev_vol_score)和新观测值决定下一状态
        if self._prev_vol_score < 0:
            # 当前在防御状态(-1), 检查是否可以退出
            if vol_20d < self.VOL_HIGH_EXIT and vol_ratio < self.VOL_RATIO_HIGH_EXIT:
                vol_score = 0.0  # 退出防御 → 中性
            else:
                vol_score = -1.0  # 维持防御
        elif self._prev_vol_score > 0:
            # 当前在进攻状态(+1), 检查是否可以退出
            if vol_20d > self.VOL_LOW_EXIT or vol_ratio > self.VOL_RATIO_LOW_EXIT:
                vol_score = 0.0  # 退出进攻 → 中性
            else:
                vol_score = 1.0  # 维持进攻
        else:
            # 当前在中性状态(0), 检查是否需要进入防御或进攻
            if vol_20d > self.VOL_HIGH_ENTER or vol_ratio > self.VOL_RATIO_HIGH_ENTER:
                vol_score = -1.0  # 高波动 → 进入防御
            elif vol_20d < self.VOL_LOW_ENTER and vol_ratio < self.VOL_RATIO_LOW_ENTER:
                vol_score = 1.0  # 低波动 → 进入进攻
            else:
                vol_score = 0.0  # 维持中性

        self._prev_vol_score = vol_score

        # 宽度评分
        breadth = features.get("breadth", 0.5)
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

        # composite简单求和: 三个维度等权, 避免人为设定复杂权重
        composite = trend_score + vol_score + breadth_score

        # 阈值设计: 1.5/0.5/-1.0, 不对称 — 进入进攻需强信号, 进入防御更敏感
        # 不对称原因: 进攻误判代价(回撤)远大于防御误判代价(踏空)
        if composite >= 1.5 and trend_score > 0:
            regime = REGIME_RISK_ON
        elif composite >= 0.5 and abs(trend_score) > 0.3:
            regime = REGIME_TRENDING
        elif composite <= -1.0:
            regime = REGIME_DEFENSIVE
        else:
            regime = REGIME_MEAN_REVERTING

        # 计算置信度: 特征越偏离中性，置信度越高
        trend_20d_abs = abs(features.get("market_trend_20d", 0))
        vol_ratio_val = features.get("vol_ratio", 1.0)
        breadth_val = features.get("breadth", 0.5)
        confidence = min((trend_20d_abs * 10 + abs(vol_ratio_val - 1.0) * 2 + abs(breadth_val - 0.5) * 2) / 3, 1.0)
        # 不设置信度下限: 让下游系统知道何时regime检测真正不确定
        # 原max(confidence, 0.3)掩盖了不确定性, 可能导致过度依赖弱信号

        logger.info(
            "Regime detected",
            extra={
                "regime": regime,
                "confidence": round(confidence, 3),
                "trend_score": round(trend_score, 3),
                "vol_score": round(vol_score, 3),
                "breadth_score": round(breadth_score, 3),
                "composite": round(composite, 3),
                "vol_20d": round(vol_20d, 4),
                "size_spread": round(size_spread, 4),
            },
        )

        return regime, confidence

    def get_weight_adjustments(self, regime: str, base_weights: dict[str, float]) -> dict[str, float]:
        """
        根据regime调整模块权重 (V2: 使用增量调整, 与EnsembleEngine一致)

        Args:
            regime: 当前市场状态
            base_weights: 基础模块权重 {module_name: weight}

        Returns:
            调整后的权重
        """
        adjustments = REGIME_WEIGHT_ADJUSTMENTS.get(regime, {})

        adjusted = {}
        for module, weight in base_weights.items():
            adj_delta = adjustments.get(module, 0.0)
            adjusted[module] = weight + adj_delta

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def detect_with_confidence(
        self, market_data: pd.DataFrame, large_cap_df: pd.DataFrame = None, small_cap_df: pd.DataFrame = None
    ) -> dict[str, Any]:
        """
        检测regime并返回置信度

        Returns:
            {regime: str, confidence: float, features: Dict, weight_adjustments: Dict}
        """
        regime, confidence = self.detect(market_data, large_cap_df, small_cap_df)
        features = self.market_features(market_data)

        base_weights = {"quality_growth": 0.35, "expectation": 0.30, "residual_momentum": 0.25, "flow_confirm": 0.10}
        adjusted_weights = self.get_weight_adjustments(regime, base_weights)

        # 增量调整（而非归一化后的绝对权重）— 前端需要显示调整幅度
        adjustments = REGIME_WEIGHT_ADJUSTMENTS.get(regime, {})

        return {
            "regime": regime,
            "confidence": round(confidence, 3),
            "features": features,
            "weight_adjustments": adjusted_weights,
            "module_weight_adjustment": adjustments,
        }
