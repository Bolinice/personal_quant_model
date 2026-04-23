"""
信号融合层
实现GPT设计9.1-9.4节: 模块分数融合、动态IC加权、Regime调权、高相关模块权重收缩
核心: S_final = Σ w_m * z(S_m), 先横截面标准化再加权
"""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.alpha_modules import AlphaModule, get_all_modules
from app.core.logging import logger


class AlphaEnsemble:
    """信号融合层 - GPT设计9.1-9.4节"""

    # GPT设计9.2节初始权重建议
    DEFAULT_WEIGHTS = {
        'price': 0.30,
        'fundamental': 0.25,
        'revision': 0.25,
        'flow_event': 0.20,
    }

    # GPT设计9.3节: Regime调权映射
    REGIME_WEIGHT_ADJUSTMENTS = {
        'trending': {
            # 趋势市: 价格/修正权重更高
            'price': 1.3, 'fundamental': 0.8, 'revision': 1.2, 'flow_event': 0.9,
        },
        'mean_reverting': {
            # 震荡市: 反转/价值权重更高
            'price': 1.2, 'fundamental': 1.3, 'revision': 0.8, 'flow_event': 0.9,
        },
        'defensive': {
            # 防御市: 质量权重更高
            'price': 0.7, 'fundamental': 1.4, 'revision': 0.8, 'flow_event': 0.6,
        },
        'risk_on': {
            # 风险偏好高: 资金/事件更高
            'price': 1.1, 'fundamental': 0.7, 'revision': 1.0, 'flow_event': 1.3,
        },
    }

    def __init__(self, modules: Optional[List[AlphaModule]] = None,
                 weights: Optional[Dict[str, float]] = None):
        """
        Args:
            modules: Alpha模块列表, None则使用全部默认模块
            weights: 模块权重, None则使用DEFAULT_WEIGHTS
        """
        self.modules = modules or get_all_modules()
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._ic_history: Dict[str, List[float]] = {m.name: [] for m in self.modules}

    def fuse(self, factor_df: pd.DataFrame,
             regime: Optional[str] = None,
             ic_history: Optional[pd.DataFrame] = None) -> Tuple[pd.Series, Dict[str, pd.Series]]:
        """
        融合各模块分数: S_final = Σ w_m * z(S_m)

        Args:
            factor_df: 因子数据
            regime: 当前市场状态 (可选, 用于调权)
            ic_history: 模块IC历史 (可选, 用于动态加权)

        Returns:
            (final_score, module_scores): 最终分数 + 各模块分数
        """
        # 1. 计算各模块分数
        module_scores = {}
        for module in self.modules:
            try:
                score = module.score(factor_df)
                if not score.empty:
                    # 横截面标准化
                    score = self._cross_sectional_zscore(score)
                    module_scores[module.name] = score
            except Exception as e:
                logger.warning(f"Module {module.name} scoring failed: {e}")

        if not module_scores:
            logger.warning("No module scores available for fusion")
            return pd.Series(0.0, index=factor_df.index), {}

        # 2. 确定权重
        current_weights = self.weights.copy()

        # 2a. 动态IC加权
        if ic_history is not None and not ic_history.empty:
            dynamic_w = self.dynamic_weights(ic_history)
            # 混合: 70%基础权重 + 30%动态权重 (避免过度切换)
            for name in current_weights:
                if name in dynamic_w:
                    current_weights[name] = 0.7 * current_weights[name] + 0.3 * dynamic_w[name]

        # 2b. Regime调权
        if regime is not None:
            current_weights = self.regime_adjust_weights(regime, current_weights)

        # 2c. 高相关模块权重收缩
        if len(module_scores) > 1:
            scores_df = pd.DataFrame(module_scores)
            current_weights = self.correlation_shrink(scores_df, current_weights)

        # 归一化权重
        total_w = sum(current_weights.values())
        if total_w > 0:
            current_weights = {k: v / total_w for k, v in current_weights.items()}

        # 3. 加权融合
        common_index = factor_df.index
        final_score = pd.Series(0.0, index=common_index)

        for name, score in module_scores.items():
            w = current_weights.get(name, 0)
            if w > 0:
                # 对齐index
                aligned = score.reindex(common_index).fillna(0)
                final_score += w * aligned

        # 4. 最终横截面标准化
        final_score = self._cross_sectional_zscore(final_score)

        logger.info(
            "Alpha ensemble fused",
            extra={
                "n_modules": len(module_scores),
                "weights": {k: round(v, 3) for k, v in current_weights.items()},
                "regime": regime,
            },
        )

        return final_score, module_scores

    def dynamic_weights(self, ic_history: pd.DataFrame,
                        window: int = 60,
                        shrinkage: float = 0.5) -> Dict[str, float]:
        """
        基于滚动IC/IR动态调权 (GPT设计9.3节)

        Args:
            ic_history: 模块IC历史, columns=模块名, index=trade_date
            window: 滚动窗口(交易日)
            shrinkage: 权重收缩系数 (防止极端权重)

        Returns:
            动态权重字典
        """
        if ic_history.empty:
            return self.weights.copy()

        # 取最近window的IC
        recent_ic = ic_history.iloc[-window:] if len(ic_history) > window else ic_history

        # 计算各模块IR (IC均值/IC标准差)
        ir = {}
        for col in recent_ic.columns:
            ic_series = recent_ic[col].dropna()
            if len(ic_series) > 10:
                ic_mean = ic_series.mean()
                ic_std = ic_series.std()
                ir[col] = ic_mean / ic_std if ic_std > 0 else 0
            else:
                ir[col] = 0

        # IR -> 权重 (正值IR才分配权重)
        positive_ir = {k: max(v, 0) for k, v in ir.items()}
        total_ir = sum(positive_ir.values())

        if total_ir == 0:
            return self.weights.copy()

        # 收缩: w = (1-shrinkage)*w_base + shrinkage*w_ir
        dynamic_w = {}
        for name in self.weights:
            w_base = self.weights[name]
            w_ir = positive_ir.get(name, 0) / total_ir
            dynamic_w[name] = (1 - shrinkage) * w_base + shrinkage * w_ir

        # 归一化
        total = sum(dynamic_w.values())
        if total > 0:
            dynamic_w = {k: v / total for k, v in dynamic_w.items()}

        return dynamic_w

    def regime_adjust_weights(self, regime: str,
                              base_weights: Dict[str, float]) -> Dict[str, float]:
        """
        Regime调权 (GPT设计9.3节)

        Args:
            regime: 市场状态 ('trending', 'mean_reverting', 'defensive', 'risk_on')
            base_weights: 基础权重

        Returns:
            调整后的权重
        """
        adjustments = self.REGIME_WEIGHT_ADJUSTMENTS.get(regime)
        if adjustments is None:
            return base_weights.copy()

        adjusted = {}
        for name, w in base_weights.items():
            adj = adjustments.get(name, 1.0)
            adjusted[name] = w * adj

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        logger.info(
            "Regime weight adjustment",
            extra={"regime": regime, "adjusted_weights": {k: round(v, 3) for k, v in adjusted.items()}},
        )

        return adjusted

    def correlation_shrink(self, module_scores: pd.DataFrame,
                           weights: Dict[str, float],
                           threshold: float = 0.7,
                           shrink_factor: float = 0.5) -> Dict[str, float]:
        """
        高相关模块权重收缩 (GPT设计9.3节)
        如果两个模块近期高度相关, 则对权重做shrink

        Args:
            module_scores: 模块分数, columns=模块名
            weights: 当前权重
            threshold: 相关性阈值
            shrink_factor: 收缩因子

        Returns:
            收缩后的权重
        """
        if module_scores.shape[1] < 2:
            return weights.copy()

        # 计算相关矩阵
        corr = module_scores.corr()

        # 找高相关对
        adjusted = weights.copy()
        modules = list(module_scores.columns)

        for i in range(len(modules)):
            for j in range(i + 1, len(modules)):
                m1, m2 = modules[i], modules[j]
                if m1 not in corr.columns or m2 not in corr.columns:
                    continue
                c = abs(corr.loc[m1, m2])
                if c > threshold and m1 in adjusted and m2 in adjusted:
                    # 两个模块高度相关, 按比例收缩较小的权重
                    if adjusted[m1] >= adjusted[m2]:
                        adjusted[m2] *= shrink_factor
                    else:
                        adjusted[m1] *= shrink_factor

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def update_ic_history(self, module_name: str, ic_value: float) -> None:
        """更新模块IC历史"""
        if module_name not in self._ic_history:
            self._ic_history[module_name] = []
        self._ic_history[module_name].append(ic_value)

    def get_ic_history_df(self) -> pd.DataFrame:
        """获取IC历史DataFrame"""
        return pd.DataFrame(self._ic_history)

    # ==================== 辅助方法 ====================

    @staticmethod
    def _cross_sectional_zscore(series: pd.Series) -> pd.Series:
        """横截面z-score标准化"""
        if isinstance(series.index, pd.MultiIndex) and series.index.nlevels >= 2:
            # 按日期(level=1)分组标准化
            return series.groupby(level=1).transform(
                lambda x: (x - x.mean()) / x.std() if x.std() > 0 else x * 0
            )
        else:
            std = series.std()
            return (series - series.mean()) / std if std > 0 else series * 0