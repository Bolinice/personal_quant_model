"""
信号融合层 V2
=============
融合五大Alpha模块信号 + 风险惩罚独立扣分

V2融合5步流程:
1. 基础权重 → 2. 动态IC加权 → 3. Regime调权 → 4. 高相关收缩 → 5. 归一化

V2权重基线:
- quality_growth: 0.35 (质量成长)
- expectation: 0.30 (预期修正)
- residual_momentum: 0.25 (残差动量)
- flow_confirm: 0.10 (资金流确认)

V2 Regime映射:
- risk_on (进攻): 质量成长↓ 动量↑ 资金流↑
- trending (趋势): 均衡
- defensive (防御): 质量↑ 动量↓
- mean_reverting (震荡): 修正↑ 动量↓

风险惩罚独立扣分: S_final = S_raw - 0.35 * P_risk

动态权重收缩: w = 0.7 * w_base + 0.3 * w_dynamic_shrunk, 限制10%-45%
"""

import logging
from datetime import date

import pandas as pd

from app.core.alpha_modules import (
    get_alpha_modules,
    get_risk_penalty_module,
)
from app.core.regime import REGIME_WEIGHT_ADJUSTMENTS

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# V2 基线权重
# ─────────────────────────────────────────────

DEFAULT_WEIGHTS: dict[str, float] = {
    "quality_growth": 0.35,  # 最高权重: 质量因子长期IC最稳定, A股超额主要来源
    "expectation": 0.30,  # 次高: 分析师修正信号对短期收益预测力强
    "residual_momentum": 0.25,  # 中等: 残差动量比原始动量更纯, 但衰减快
    "flow_confirm": 0.10,  # 最低: 资金流噪音大, 仅作确认信号避免虚假突破
}

# 权重边界: 单模块权重 ∈ [MIN_WEIGHT, MAX_WEIGHT]
MIN_WEIGHT = 0.10  # 防止任一模块完全失效, 保留最低信号贡献
MAX_WEIGHT = 0.45  # 防止单模块独大导致集中度风险

# 动态收缩系数: w = SHRINK_BASE * w_base + (1 - SHRINK_BASE) * w_dynamic
SHRINK_BASE = 0.70  # 0.7基线权重收缩: 信任历史基线多于短期IC, 避免过拟合近期

# 风险惩罚系数
RISK_LAMBDA = 0.35  # 惩罚强度: 使风险厌恶与alpha激励大致等量级


# ─────────────────────────────────────────────
# V2 Regime权重调整映射 (单一来源: app.core.regime)
# ─────────────────────────────────────────────
# REGIME_WEIGHT_ADJUSTMENTS 从 app.core.regime 导入, 避免重复定义


# ─────────────────────────────────────────────
# 融合引擎
# ─────────────────────────────────────────────


class EnsembleEngine:
    """
    V2信号融合引擎

    5步融合流程:
    1. 基础权重初始化
    2. 动态IC加权 (基于滚动IC)
    3. Regime调权
    4. 高相关收缩 (模块间高相关时向基线收缩)
    5. 归一化

    最终: S_final = S_raw - λ * P_risk
    """

    def __init__(
        self,
        base_weights: dict[str, float] | None = None,
        risk_lambda: float = RISK_LAMBDA,
        shrink_base: float = SHRINK_BASE,
        min_weight: float = MIN_WEIGHT,
        max_weight: float = MAX_WEIGHT,
    ):
        self.base_weights = base_weights or DEFAULT_WEIGHTS.copy()
        self.risk_lambda = risk_lambda
        self.shrink_base = shrink_base
        self.min_weight = min_weight
        self.max_weight = max_weight

        # Alpha模块
        self.alpha_modules = get_alpha_modules()
        self.risk_module = get_risk_penalty_module()

    def compute_module_scores(self, df: pd.DataFrame, **kwargs) -> dict[str, pd.Series]:
        """计算所有Alpha模块得分"""
        module_scores = {}
        for name, module in self.alpha_modules.items():
            try:
                scores = module.compute_scores(df, **kwargs)
                module_scores[name] = scores
            except Exception as e:
                logger.error(f"[Ensemble] 模块 {name} 计算失败: {e}")
                module_scores[name] = pd.Series(0.0, index=df.index)  # 模块失败不阻断, 零分中性化处理
        return module_scores

    def compute_risk_penalty(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        """计算风险惩罚得分"""
        try:
            return self.risk_module.compute_scores(df, **kwargs)
        except Exception as e:
            logger.error(f"[Ensemble] 风险惩罚模块计算失败: {e}")
            return pd.Series(0.0, index=df.index)

    def step1_base_weights(self) -> dict[str, float]:
        """Step 1: 基础权重"""
        return self.base_weights.copy()

    def step2_dynamic_ic_weights(
        self,
        base_weights: dict[str, float],
        ic_dict: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """
        Step 2: 动态IC加权

        基于滚动IC调整权重:
        - IC > 0: 权重上调
        - IC < 0: 权重下调
        - IC缺失: 使用基础权重

        Args:
            base_weights: 基础权重
            ic_dict: 各模块的滚动IC值 {module_name: ic_value}
        """
        if ic_dict is None:
            return base_weights.copy()

        dynamic_weights = {}
        for name, base_w in base_weights.items():
            ic = ic_dict.get(name, 0.0)
            # IC调整幅度: IC * 0.3 (IC=0.1 → +3%)
            # 系数0.3控制IC对权重的边际影响, 避免短期IC噪声导致权重剧烈漂移
            adjustment = ic * 0.3
            dynamic_weights[name] = base_w + adjustment

        return dynamic_weights

    def step3_regime_adjustment(
        self,
        weights: dict[str, float],
        regime: str = "trending",
    ) -> dict[str, float]:
        """
        Step 3: Regime调权

        根据市场状态调整模块权重
        """
        adjustments = REGIME_WEIGHT_ADJUSTMENTS.get(regime, {})
        adjusted = {}
        for name, w in weights.items():
            adj = adjustments.get(name, 0.0)
            adjusted[name] = w + adj
        return adjusted

    def step4_correlation_shrinkage(
        self,
        weights: dict[str, float],
        module_corr: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        """
        Step 4: 高相关收缩

        当模块间相关性过高时, 将动态权重向基线收缩
        收缩公式: w = shrink_base * w_base + (1 - shrink_base) * w_dynamic
        """
        if module_corr is None:
            # 无相关性信息时, 轻微收缩 (保守策略: 缺少数据时更依赖基线)
            shrunk = {}
            for name, w in weights.items():
                base_w = self.base_weights.get(name, 0.25)
                shrunk[name] = self.shrink_base * base_w + (1 - self.shrink_base) * w
            return shrunk

        # 计算平均相关系数
        n = len(module_corr)
        if n < 2:
            return weights.copy()

        total_corr = 0.0
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                total_corr += abs(module_corr.iloc[i, j])
                count += 1

        avg_corr = total_corr / count if count > 0 else 0.0

        # 相关性越高, 收缩越强 (高相关意味着模块信号冗余, 应更信任基线权重)
        effective_shrink = min(1.0, self.shrink_base + 0.3 * avg_corr)

        shrunk = {}
        for name, w in weights.items():
            base_w = self.base_weights.get(name, 0.25)
            shrunk[name] = effective_shrink * base_w + (1 - effective_shrink) * w

        return shrunk

    def step5_normalize(self, weights: dict[str, float]) -> dict[str, float]:
        """
        Step 5: 归一化 + 权重边界约束

        - 单模块权重 ∈ [min_weight, max_weight]
        - 所有模块权重之和 = 1.0
        """
        # 边界约束
        constrained = {}
        for name, w in weights.items():
            constrained[name] = max(self.min_weight, min(self.max_weight, w))

        # 归一化
        total = sum(constrained.values())
        if total > 0:
            constrained = {k: v / total for k, v in constrained.items()}

        return constrained

    def fuse(
        self,
        df: pd.DataFrame,
        regime: str = "trending",
        ic_dict: dict[str, float] | None = None,
        module_corr: pd.DataFrame | None = None,
        apply_risk_penalty: bool = True,
        precomputed_module_scores: dict[str, pd.Series] | None = None,
        precomputed_risk_penalty: pd.Series | None = None,
        **kwargs,
    ) -> tuple[pd.Series, dict]:
        """
        完整V2融合流程

        Args:
            df: 包含所有因子数据的DataFrame
            regime: 当前市场状态
            ic_dict: 各模块滚动IC
            module_corr: 模块间相关系数矩阵
            apply_risk_penalty: 是否应用风险惩罚
            precomputed_module_scores: 预计算的Alpha模块得分(避免重复计算)
            precomputed_risk_penalty: 预计算的风险惩罚得分

        Returns:
            (final_scores, meta_info)
            - final_scores: 最终综合得分Series
            - meta_info: 融合元信息(各步权重、模块得分等)
        """
        meta = {}

        # 计算各模块得分 (使用预计算结果或重新计算)
        if precomputed_module_scores is not None:
            module_scores = precomputed_module_scores
        else:
            module_scores = self.compute_module_scores(df, **kwargs)
        meta["module_scores"] = {k: v.to_dict() for k, v in module_scores.items()}

        # Step 1: 基础权重
        weights = self.step1_base_weights()
        meta["step1_base_weights"] = weights.copy()

        # Step 2: 动态IC加权
        weights = self.step2_dynamic_ic_weights(weights, ic_dict)
        meta["step2_ic_weights"] = weights.copy()

        # Step 3: Regime调权
        weights = self.step3_regime_adjustment(weights, regime)
        meta["step3_regime_weights"] = weights.copy()

        # Step 4: 高相关收缩
        weights = self.step4_correlation_shrinkage(weights, module_corr)
        meta["step4_shrunk_weights"] = weights.copy()

        # Step 5: 归一化
        weights = self.step5_normalize(weights)
        meta["step5_final_weights"] = weights.copy()

        # 加权融合
        raw_score = pd.Series(0.0, index=df.index)
        for name, w in weights.items():
            if name in module_scores:
                raw_score += w * module_scores[name]  # 加权求和: 各模块得分已归一化, 直接加权即可

        meta["raw_score_stats"] = {
            "mean": float(raw_score.mean()),
            "std": float(raw_score.std()),
            "min": float(raw_score.min()),
            "max": float(raw_score.max()),
        }

        # 风险惩罚独立扣分: 不参与加权融合, 避免风险因子与alpha因子互相稀释
        if apply_risk_penalty:
            risk_penalty = self.compute_risk_penalty(df, **kwargs)
            final_score = raw_score - self.risk_lambda * risk_penalty
            meta["risk_penalty_stats"] = {
                "mean": float(risk_penalty.mean()),
                "std": float(risk_penalty.std()),
                "lambda": self.risk_lambda,
            }
        else:
            final_score = raw_score

        meta["final_score_stats"] = {
            "mean": float(final_score.mean()),
            "std": float(final_score.std()),
            "min": float(final_score.min()),
            "max": float(final_score.max()),
        }

        return final_score, meta

    def combine(
        self,
        factor_df: pd.DataFrame,
        factor_names: list[str],
        trade_date: date | None = None,
        regime: str = "trending",
        ic_dict: dict[str, float] | None = None,
        module_corr: pd.DataFrame | None = None,
    ) -> tuple[pd.Series, dict[str, float]]:
        """
        便捷融合方法 — daily_pipeline调用入口

        Returns:
            (final_scores, final_weights) — 与fuse()不同, 只返回得分和权重
        """
        final_score, meta = self.fuse(
            factor_df,
            regime=regime,
            ic_dict=ic_dict,
            module_corr=module_corr,
        )
        final_weights = meta.get("step5_final_weights", {})
        return final_score, final_weights


# ─────────────────────────────────────────────
# 便捷函数
# ─────────────────────────────────────────────


def get_default_weights() -> dict[str, float]:
    """获取V2默认权重"""
    return DEFAULT_WEIGHTS.copy()


def get_regime_adjustments() -> dict[str, dict[str, float]]:
    """获取Regime权重调整映射"""
    return REGIME_WEIGHT_ADJUSTMENTS.copy()


def create_ensemble_engine(**kwargs) -> EnsembleEngine:
    """创建融合引擎"""
    return EnsembleEngine(**kwargs)
