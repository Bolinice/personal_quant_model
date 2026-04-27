"""
Alpha模块化架构 V2
===================
五大Alpha模块 + 一大风险惩罚模块:
1. QualityGrowthModule  — 质量成长 (权重35%)
2. ExpectationModule    — 预期修正 (权重30%)
3. ResidualMomentumModule — 残差动量 (权重25%)
4. FlowConfirmModule    — 资金流确认 (权重10%)
5. RiskPenaltyModule    — 风险惩罚 (独立扣分, λ=0.35)

V2变更:
- 从4模块(price/fundamental/revision/flow_event)升级为5+1模块
- 质量成长模块整合了原price+fundamental的核心因子
- 预期修正模块整合了原revision的修正信号
- 残差动量模块替代原price中的简单动量
- 资金流确认模块替代原flow_event
- 新增风险惩罚模块作为独立扣分层
"""

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# FactorPreprocessor 单例 (无状态, 避免每次调用重复创建)
# ─────────────────────────────────────────────

def _get_factor_preprocessor():
    """延迟导入并缓存 FactorPreprocessor 单例"""
    from app.core.factor_preprocess import FactorPreprocessor
    if not hasattr(_get_factor_preprocessor, '_instance'):
        _get_factor_preprocessor._instance = FactorPreprocessor()
    return _get_factor_preprocessor._instance


# ─────────────────────────────────────────────
# 基类
# ─────────────────────────────────────────────

class AlphaModuleBase(ABC):
    """Alpha模块基类"""

    name: str = ""
    display_name: str = ""
    description: str = ""

    @abstractmethod
    def get_factor_names(self) -> List[str]:
        """返回模块包含的因子名称列表"""
        ...

    def compute_scores(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        """计算模块得分 — 默认实现: 遍历FACTOR_CONFIG加权融合"""
        scores = pd.Series(0.0, index=df.index)
        active_weight = 0.0

        for factor_name, config in self.FACTOR_CONFIG.items():
            if factor_name not in df.columns:
                logger.warning(f"[{self.name}] 因子 {factor_name} 缺失, 跳过")
                continue

            raw = df[factor_name].copy()
            if config["direction"] == -1:
                raw = -raw
            processed = self.preprocess_factor(raw)
            scores += config["weight"] * processed
            active_weight += config["weight"]

        # 按实际可用权重归一化
        if active_weight > 0 and active_weight < 0.99:
            scores = scores / active_weight

        return scores

    def preprocess_factor(
        self,
        series: pd.Series,
        mad_threshold: float = 3.0,
        zscore: bool = True,
    ) -> pd.Series:
        """因子预处理: 去极值(MAD) → 标准化(Z-score) — 委托给FactorPreprocessor单例"""
        fp = _get_factor_preprocessor()
        result = fp.winsorize_mad(series, mad_threshold)
        if zscore:
            result = fp.standardize_zscore(result)
        return result


# ─────────────────────────────────────────────
# 1. 质量成长模块 (权重35%)
# ─────────────────────────────────────────────

class QualityGrowthModule(AlphaModuleBase):
    """
    质量成长模块 — 权重35%

    核心逻辑: 筛选盈利能力强、成长性高且财务质量好的公司
    因子组:
      - ROE_ttm: 净资产收益率TTM (方向+)
      - ROE_delta: ROE同比变化 (方向+)
      - gross_margin: 毛利率 (方向+)
      - revenue_growth_yoy: 营收同比增长率 (方向+)
      - profit_growth_yoy: 净利润同比增长率 (方向+)
      - operating_cashflow_ratio: 经营现金流/净利润 (方向+)
      - accrual_ratio: 应计利润比率 (方向-)
    """

    name = "quality_growth"
    display_name = "质量成长"
    description = "盈利能力强、成长性高且财务质量好的公司"

    FACTOR_CONFIG = {
        "roe_ttm": {"direction": 1, "weight": 0.20},
        "roe_delta": {"direction": 1, "weight": 0.15},
        "gross_margin": {"direction": 1, "weight": 0.10},
        "revenue_growth_yoy": {"direction": 1, "weight": 0.15},
        "profit_growth_yoy": {"direction": 1, "weight": 0.15},
        "operating_cashflow_ratio": {"direction": 1, "weight": 0.15},
        "accrual_ratio": {"direction": -1, "weight": 0.10},
    }

    def get_factor_names(self) -> List[str]:
        return list(self.FACTOR_CONFIG.keys())


# ─────────────────────────────────────────────
# 2. 预期修正模块 (权重30%)
# ─────────────────────────────────────────────

class ExpectationModule(AlphaModuleBase):
    """
    预期修正模块 — 权重30%

    核心逻辑: 捕捉分析师预期上修和业绩预告超预期信号
    因子组:
      - eps_revision_fy0: FY0 EPS修正幅度 (方向+)
      - eps_revision_fy1: FY1 EPS修正幅度 (方向+)
      - analyst_coverage: 分析师覆盖数 (方向+)
      - rating_upgrade_ratio: 评级上调比例 (方向+)
      - earnings_surprise: 业绩超预期幅度 (方向+)
      - guidance_up_ratio: 业绩预告上修比例 (方向+)
    """

    name = "expectation"
    display_name = "预期修正"
    description = "分析师预期上修和业绩预告超预期信号"

    FACTOR_CONFIG = {
        "eps_revision_fy0": {"direction": 1, "weight": 0.25},
        "eps_revision_fy1": {"direction": 1, "weight": 0.20},
        "analyst_coverage": {"direction": 1, "weight": 0.10},
        "rating_upgrade_ratio": {"direction": 1, "weight": 0.15},
        "earnings_surprise": {"direction": 1, "weight": 0.20},
        "guidance_up_ratio": {"direction": 1, "weight": 0.10},
    }

    def get_factor_names(self) -> List[str]:
        return list(self.FACTOR_CONFIG.keys())


# ─────────────────────────────────────────────
# 3. 残差动量模块 (权重25%)
# ─────────────────────────────────────────────

class ResidualMomentumModule(AlphaModuleBase):
    """
    残差动量模块 — 权重25%

    核心逻辑: 剥离风格因子后的残差收益动量, 比原始动量更稳健
    因子组:
      - residual_return_20d: 20日残差收益率 (方向+)
      - residual_return_60d: 60日残差收益率 (方向+)
      - residual_return_120d: 120日残差收益率 (方向+)
      - residual_sharpe: 残差夏普比率 (方向+)
      - turnover_ratio_20d: 20日换手率 (方向-, 高换手削弱动量)
      - max_drawdown_20d: 20日最大回撤 (方向-)
    """

    name = "residual_momentum"
    display_name = "残差动量"
    description = "剥离风格因子后的残差收益动量"

    FACTOR_CONFIG = {
        "residual_return_20d": {"direction": 1, "weight": 0.25},
        "residual_return_60d": {"direction": 1, "weight": 0.30},
        "residual_return_120d": {"direction": 1, "weight": 0.15},
        "residual_sharpe": {"direction": 1, "weight": 0.15},
        "turnover_ratio_20d": {"direction": -1, "weight": 0.10},
        "max_drawdown_20d": {"direction": -1, "weight": 0.05},
    }

    def get_factor_names(self) -> List[str]:
        return list(self.FACTOR_CONFIG.keys())


# ─────────────────────────────────────────────
# 4. 资金流确认模块 (权重10%)
# ─────────────────────────────────────────────

class FlowConfirmModule(AlphaModuleBase):
    """
    资金流确认模块 — 权重10%

    核心逻辑: 确认价格趋势是否有资金面支撑
    因子组:
      - north_net_inflow_5d: 5日北向净流入 (方向+)
      - north_net_inflow_20d: 20日北向净流入 (方向+)
      - main_force_net_inflow: 主力净流入 (方向+)
      - large_order_net_ratio: 大单净占比 (方向+)
      - margin_balance_change: 融资余额变化率 (方向+)
      - institutional_holding_change: 机构持仓变化 (方向+)
    """

    name = "flow_confirm"
    display_name = "资金流确认"
    description = "确认价格趋势是否有资金面支撑"

    FACTOR_CONFIG = {
        "north_net_inflow_5d": {"direction": 1, "weight": 0.20},
        "north_net_inflow_20d": {"direction": 1, "weight": 0.15},
        "main_force_net_inflow": {"direction": 1, "weight": 0.20},
        "large_order_net_ratio": {"direction": 1, "weight": 0.20},
        "margin_balance_change": {"direction": 1, "weight": 0.10},
        "institutional_holding_change": {"direction": 1, "weight": 0.15},
    }

    def get_factor_names(self) -> List[str]:
        return list(self.FACTOR_CONFIG.keys())


# ─────────────────────────────────────────────
# 5. 风险惩罚模块 (独立扣分, λ=0.35)
# ─────────────────────────────────────────────

class RiskPenaltyModule(AlphaModuleBase):
    """
    风险惩罚模块 — 独立扣分层, λ=0.35

    核心逻辑: 不参与加权融合, 而是作为独立扣分层
    S_final = S_raw - λ * P_risk

    风险因子组:
      - volatility_20d: 20日波动率 (方向-, 高波动惩罚)
      - idiosyncratic_vol: 特质波动率 (方向-)
      - max_drawdown_60d: 60日最大回撤 (方向-)
      - illiquidity: 非流动性 (方向-, Amihud比率)
      - concentration_top10: 前十大股东集中度 (方向-)
      - pledge_ratio: 股权质押比例 (方向-)
      - goodwill_ratio: 商誉/净资产 (方向-)
    """

    name = "risk_penalty"
    display_name = "风险惩罚"
    description = "独立风险扣分层, 不参与加权融合"

    LAMBDA = 0.35  # 风险惩罚系数

    FACTOR_CONFIG = {
        "volatility_20d": {"direction": -1, "weight": 0.20},
        "idiosyncratic_vol": {"direction": -1, "weight": 0.20},
        "max_drawdown_60d": {"direction": -1, "weight": 0.15},
        "illiquidity": {"direction": -1, "weight": 0.15},
        "concentration_top10": {"direction": -1, "weight": 0.10},
        "pledge_ratio": {"direction": -1, "weight": 0.10},
        "goodwill_ratio": {"direction": -1, "weight": 0.10},
    }

    def get_factor_names(self) -> List[str]:
        return list(self.FACTOR_CONFIG.keys())

    def compute_scores(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        """
        计算风险惩罚得分 P_risk ∈ [0, 1]
        注意: 返回的是风险惩罚分, 需要在外部做 S_final = S_raw - λ * P_risk
        """
        scores = pd.Series(0.0, index=df.index)
        active_weight = 0.0

        for factor_name, config in self.FACTOR_CONFIG.items():
            if factor_name not in df.columns:
                logger.warning(f"[RiskPenalty] 因子 {factor_name} 缺失, 跳过")
                continue

            raw = df[factor_name].copy()
            # 风险因子方向为负(高风险→高惩罚), 取反后正值表示风险
            if config["direction"] == -1:
                raw = -raw
            processed = self.preprocess_factor(raw)
            scores += config["weight"] * processed
            active_weight += config["weight"]

        if active_weight > 0 and active_weight < 0.99:
            scores = scores / active_weight

        # 将惩罚分映射到 [0, 1] 区间 (sigmoid压缩)
        penalty = 1.0 / (1.0 + np.exp(-scores))
        return penalty


# ─────────────────────────────────────────────
# 模块注册表
# ─────────────────────────────────────────────

MODULE_REGISTRY: Dict[str, AlphaModuleBase] = {
    "quality_growth": QualityGrowthModule(),
    "expectation": ExpectationModule(),
    "residual_momentum": ResidualMomentumModule(),
    "flow_confirm": FlowConfirmModule(),
    "risk_penalty": RiskPenaltyModule(),
}


def get_module(name: str) -> Optional[AlphaModuleBase]:
    """获取指定模块"""
    return MODULE_REGISTRY.get(name)


def get_alpha_modules() -> Dict[str, AlphaModuleBase]:
    """获取所有Alpha模块(不含风险惩罚)"""
    return {k: v for k, v in MODULE_REGISTRY.items() if k != "risk_penalty"}


def get_risk_penalty_module() -> RiskPenaltyModule:
    """获取风险惩罚模块"""
    return MODULE_REGISTRY["risk_penalty"]


def get_all_modules() -> Dict[str, AlphaModuleBase]:
    """获取所有模块"""
    return MODULE_REGISTRY.copy()
