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

import logging
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# FactorPreprocessor 单例 (无状态, 避免每次调用重复创建)
# 无状态设计: FactorPreprocessor不含股票/日期等上下文, 只有方法, 可安全复用
# ─────────────────────────────────────────────


def _get_factor_preprocessor():
    """延迟导入并缓存 FactorPreprocessor 单例"""
    from app.core.factor_preprocess import FactorPreprocessor

    if not hasattr(_get_factor_preprocessor, "_instance"):
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
    def get_factor_names(self) -> list[str]:
        """返回模块包含的因子名称列表"""
        ...

    def compute_scores(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        """计算模块得分 — 默认实现: 遍历FACTOR_CONFIG加权融合"""
        # 模块内等权/近似等权: 因子间IC差异不稳定, 强权重差异容易过拟合
        # 跨模块权重(ensemble层)才做差异化, 模块内保持稳健
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
        # 因子缺失时归一化: 避免缺失因子导致得分系统性偏低
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
        # 先MAD后Z-score: MAD先裁掉尾部极端值, 否则极端值会严重拉偏Z-score的均值和标准差
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
        "roe_ttm": {"direction": 1, "weight": 0.20},  # 权重最高: ROE是A股最稳定的alpha来源
        "roe_delta": {"direction": 1, "weight": 0.15},  # ROE变化而非绝对值: 边际改善比绝对水平更有预测力
        "gross_margin": {"direction": 1, "weight": 0.10},  # 毛利率: 反映定价权和成本控制, 但行业差异大权重偏低
        "revenue_growth_yoy": {"direction": 1, "weight": 0.15},
        "profit_growth_yoy": {"direction": 1, "weight": 0.15},
        "operating_cashflow_ratio": {
            "direction": 1,
            "weight": 0.15,
        },  # 现金流/净利润: 识别盈余质量, 高应计利润往往伴随盈利操纵
        "accrual_ratio": {"direction": -1, "weight": 0.10},  # 方向-1: 应计利润越高, 未来收益越差(Sloan异象)
    }

    def get_factor_names(self) -> list[str]:
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
        "eps_revision_fy0": {"direction": 1, "weight": 0.25},  # FY0修正: 当年EPS修正最直接, 预测力最强
        "eps_revision_fy1": {"direction": 1, "weight": 0.20},  # FY1修正: 次年预期, 反映中长期信心变化
        "analyst_coverage": {"direction": 1, "weight": 0.10},  # 覆盖数: 更多分析师关注 → 信息效率更高
        "rating_upgrade_ratio": {"direction": 1, "weight": 0.15},
        "earnings_surprise": {"direction": 1, "weight": 0.20},  # 业绩超预期: PEAD(盈余公告后漂移)是经典异象
        "guidance_up_ratio": {"direction": 1, "weight": 0.10},
    }

    def get_factor_names(self) -> list[str]:
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
        "residual_return_20d": {"direction": 1, "weight": 0.25},  # 20日: 捕捉月度级动量
        "residual_return_60d": {"direction": 1, "weight": 0.30},  # 60日: 权重最高, A股3个月动量效应最显著
        "residual_return_120d": {"direction": 1, "weight": 0.15},  # 120日: 半年动量, 权重低因信号衰减快
        "residual_sharpe": {"direction": 1, "weight": 0.15},  # 残差夏普: 兼顾收益与波动, 风险调整后的动量
        "turnover_ratio_20d": {
            "direction": -1,
            "weight": 0.10,
        },  # 方向-1: 高换手削弱动量(A股特有: 高换手=投机, 动量不可持续)
        "max_drawdown_20d": {"direction": -1, "weight": 0.05},  # 方向-1: 近期大回撤意味着风险尚未释放
    }

    def get_factor_names(self) -> list[str]:
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
        "north_net_inflow_5d": {"direction": 1, "weight": 0.20},  # 5日北向: 短期外资动向, 对白马股定价权大
        "north_net_inflow_20d": {"direction": 1, "weight": 0.15},  # 20日北向: 中期趋势, 权重低因外资有滞后性
        "main_force_net_inflow": {"direction": 1, "weight": 0.20},  # 主力资金: 大单净流入代表机构行为
        "large_order_net_ratio": {"direction": 1, "weight": 0.20},  # 大单占比: 与主力互为补充, 度量维度不同
        "margin_balance_change": {"direction": 1, "weight": 0.10},  # 融资余额: 杠杆资金是情绪放大器, 权重低因噪声大
        "institutional_holding_change": {"direction": 1, "weight": 0.15},  # 机构持仓变化: 季频披露, 信号滞后但可靠
    }

    def get_factor_names(self) -> list[str]:
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

    LAMBDA = 0.35  # 风险惩罚系数 — 使风险扣分与alpha得分量级匹配

    FACTOR_CONFIG = {
        "volatility_20d": {"direction": -1, "weight": 0.20},  # 短期波动率: 高波动=高风险, 直接惩罚
        "idiosyncratic_vol": {
            "direction": -1,
            "weight": 0.20,
        },  # 特质波动率: 无法被系统性风险解释的波动, A股IVOL异象显著
        "max_drawdown_60d": {"direction": -1, "weight": 0.15},  # 60日最大回撤: 尾部风险度量, 惩罚极端下行
        "illiquidity": {"direction": -1, "weight": 0.15},  # Amihud非流动性: 流动性差 → 冲击成本高, 且非流动性溢价不可靠
        "concentration_top10": {"direction": -1, "weight": 0.10},  # 前十大集中度: 高集中 → 治理风险, 减持冲击大
        "pledge_ratio": {"direction": -1, "weight": 0.10},  # 股权质押比例: 高质押 → 强平风险, A股质押爆仓事件频发
        "goodwill_ratio": {"direction": -1, "weight": 0.10},  # 商誉/净资产: 高商誉 → 并购整合风险, 减值压力
    }

    def get_factor_names(self) -> list[str]:
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
        # sigmoid而非min-max: sigmoid对极端值鲁棒, 不会因单只股票异常值压缩整体分布
        return 1.0 / (1.0 + np.exp(-scores))


# ─────────────────────────────────────────────
# 模块注册表
# 注册表模式: 解耦模块定义与使用, 方便新增/替换模块而不修改下游代码
# ─────────────────────────────────────────────

MODULE_REGISTRY: dict[str, AlphaModuleBase] = {
    "quality_growth": QualityGrowthModule(),
    "expectation": ExpectationModule(),
    "residual_momentum": ResidualMomentumModule(),
    "flow_confirm": FlowConfirmModule(),
    "risk_penalty": RiskPenaltyModule(),
}


def get_module(name: str) -> AlphaModuleBase | None:
    """获取指定模块"""
    return MODULE_REGISTRY.get(name)


def get_alpha_modules() -> dict[str, AlphaModuleBase]:
    """获取所有Alpha模块(不含风险惩罚)"""
    return {k: v for k, v in MODULE_REGISTRY.items() if k != "risk_penalty"}


def get_risk_penalty_module() -> RiskPenaltyModule:
    """获取风险惩罚模块"""
    return MODULE_REGISTRY["risk_penalty"]


def get_all_modules() -> dict[str, AlphaModuleBase]:
    """获取所有模块"""
    return MODULE_REGISTRY.copy()
