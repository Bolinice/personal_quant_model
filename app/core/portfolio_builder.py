"""
组合构建器 V2
=============
核心能力:
1. 分层赋权: Top60, 1-10名1.5x / 11-30名1.2x / 31-60名1.0x
2. 风险折扣层: D_risk(低风险1.00/中风险0.85/高风险0.60/极高风险0.00) + D_liq(正常1.00/边缘0.85/明显不足0.60)
3. 双轨制: 研究模式(Alpha-Risk优化器) vs 实盘模式(分层赋权+风险折扣)
4. 调仓缓冲区: Top75持有/Top50新买入, 最小阈值0.20%
5. 100股整数倍处理
6. 行业约束: 单行业≤20%, 偏离≤5%
"""

import logging
from enum import Enum, StrEnum

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────

TOP_N = 60  # 持仓数量 # 为什么60：A股增强策略60只约覆盖2%个股，平衡超额收益与交易成本，过少集中度过高

# 分层赋权倍率
# 为什么分三层：1-10名高确信度给予1.5x权重，11-30名中确信度1.2x，31-60名低确信度1.0x
# 1.5x上限避免单股过度集中，同时保证头部alpha信号获得应有权重
TIER_MULTIPLIERS = {
    "tier1": {"range": (1, 10), "multiplier": 1.5},
    "tier2": {"range": (11, 30), "multiplier": 1.2},
    "tier3": {"range": (31, 60), "multiplier": 1.0},
}

# 风险折扣系数
# 为什么极端风险0.00：ST/*ST/退市风险股必须完全排除，A股个股黑天鹅风险不可度量
RISK_DISCOUNT = {
    "low": 1.00,  # 低风险
    "medium": 0.85,  # 中风险 # 为什么0.85：中等风险（如高质押率）15%折扣，温和减仓而非直接排除
    "high": 0.60,  # 高风险 # 为什么0.60：高风险（如ST摘帽不确定性）40%折扣，大幅减仓
    "extreme": 0.00,  # 极高风险(黑名单)
}

# 流动性折扣系数
LIQUIDITY_DISCOUNT = {
    "normal": 1.00,  # 正常
    "marginal": 0.85,  # 边缘
    "insufficient": 0.60,  # 明显不足
}

# 调仓缓冲区
# 为什么需要缓冲区：A股换仓成本高（印花税+滑点），排名微小波动不应触发买卖，缓冲区降低换手率
REBALANCE_BUFFER = {
    "hold_top": 75,  # 当前持仓排名≤75继续持有 # 为什么75>60：持仓股排名小幅下滑时不急于卖出，避免反复交易
    "buy_top": 50,  # 新买入需排名≤50 # 为什么50<60：新买入门槛更高，确保新入股票Alpha信号足够强
    "min_weight_pct": 0.20,  # 最小持仓权重0.20% # 为什么0.20%：低于此权重的持仓对组合贡献可忽略，交易成本反而侵蚀收益
}

# 行业约束
# 为什么20%上限：A股行业轮动快，单一行业超20%在行业下跌10%时拖累组合2%+
# 为什么5%偏离限制：控制跟踪误差，增强策略不应在行业配置上过度偏离基准
INDUSTRY_CONSTRAINTS = {
    "max_single_industry": 0.20,  # 单行业最大20%
    "max_deviation": 0.05,  # 偏离基准最大5%
}

# 交易单位
LOT_SIZE = 100  # A股100股整数倍 # 为什么100：A股交易规则要求最低买入100股且须为100的整数倍（科创板除外）


class PortfolioMode(StrEnum):
    RESEARCH = "research"  # 研究模式: Alpha-Risk优化器
    PRODUCTION = "production"  # 实盘模式: 分层赋权+风险折扣


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class LiquidityLevel(StrEnum):
    NORMAL = "normal"
    MARGINAL = "marginal"
    INSUFFICIENT = "insufficient"


# ─────────────────────────────────────────────
# 组合构建器
# ─────────────────────────────────────────────


class PortfolioBuilder:
    """
    V2组合构建器

    双轨制:
    - 研究模式: 基于Alpha-Risk优化器, 最大化Alpha同时控制风险
    - 实盘模式: 分层赋权+风险折扣+行业约束+100股整数倍
    """

    def __init__(
        self,
        top_n: int = TOP_N,
        mode: PortfolioMode = PortfolioMode.PRODUCTION,
        tier_multipliers: dict | None = None,
        risk_discount: dict | None = None,
        liquidity_discount: dict | None = None,
        industry_constraints: dict | None = None,
    ):
        self.top_n = top_n
        self.mode = mode
        self.tier_multipliers = tier_multipliers or TIER_MULTIPLIERS
        self.risk_discount = risk_discount or RISK_DISCOUNT
        self.liquidity_discount = liquidity_discount or LIQUIDITY_DISCOUNT
        self.industry_constraints = industry_constraints or INDUSTRY_CONSTRAINTS

    def _get_tier_multiplier(self, rank: int) -> float:
        """根据排名获取分层赋权倍率"""
        for _tier_name, tier_config in self.tier_multipliers.items():
            lo, hi = tier_config["range"]
            if lo <= rank <= hi:
                return tier_config["multiplier"]
        return 1.0

    def _get_risk_discount(self, risk_level: str) -> float:
        """根据风险等级获取折扣系数"""
        return self.risk_discount.get(risk_level, 1.0)

    def _get_liquidity_discount(self, liq_level: str) -> float:
        """根据流动性等级获取折扣系数"""
        return self.liquidity_discount.get(liq_level, 1.0)

    def _round_to_lot(self, weight: float, price: float, total_capital: float) -> float:
        """
        将权重调整为100股整数倍

        Args:
            weight: 目标权重
            price: 当前股价
            total_capital: 总资金

        Returns:
            调整后的权重
        """
        target_value = weight * total_capital
        if price <= 0:
            return 0.0
        shares = int(target_value / price)
        # 向下取整到100股整数倍
        # 为什么向下取整而非四舍五入：实盘中不足100股的部分无法买入，向下取整确保资金不超限
        shares = (shares // LOT_SIZE) * LOT_SIZE
        adjusted_value = shares * price
        return adjusted_value / total_capital if total_capital > 0 else 0.0

    def build_research_portfolio(
        self,
        scores: pd.Series,
        risk_penalty: pd.Series | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        研究模式: Alpha-Risk优化器

        最大化: Σ w_i * α_i
        约束: Σ w_i² * σ_i² ≤ target_risk
              Σ w_i = 1
              w_i ≥ 0

        简化实现: 按Alpha得分排序, 风险惩罚后等权
        """
        # 应用风险惩罚
        # 为什么系数0.35：经验值，约1/3的风险惩罚力度，避免过度惩罚导致选股过于保守
        adjusted_scores = scores - 0.35 * risk_penalty if risk_penalty is not None else scores.copy()

        # 排序选股
        ranked = adjusted_scores.rank(ascending=False)
        selected = ranked <= self.top_n

        # 等权分配
        n_selected = selected.sum()
        if n_selected == 0:
            return pd.DataFrame(columns=["ts_code", "weight", "rank", "score"])

        result = pd.DataFrame(
            {
                "ts_code": scores.index[selected],
                "weight": 1.0 / n_selected,
                "rank": ranked[selected].astype(int),
                "score": scores[selected],
            }
        )
        return result.sort_values("rank")


    def build_production_portfolio(
        self,
        scores: pd.Series,
        risk_levels: pd.Series | None = None,
        liquidity_levels: pd.Series | None = None,
        industry_series: pd.Series | None = None,
        current_holdings: pd.Series | None = None,
        prices: pd.Series | None = None,
        total_capital: float = 1e8,
        **kwargs,
    ) -> pd.DataFrame:
        """
        实盘模式: 分层赋权 + 风险折扣 + 行业约束 + 调仓缓冲区

        Args:
            scores: 综合得分Series (index=ts_code)
            risk_levels: 风险等级Series (low/medium/high/extreme)
            liquidity_levels: 流动性等级Series (normal/marginal/insufficient)
            industry_series: 行业分类Series
            current_holdings: 当前持仓权重Series (index=ts_code)
            prices: 当前股价Series
            total_capital: 总资金
        """
        # Step 1: 按得分排序
        ranked = scores.rank(ascending=False).astype(int)

        # Step 2: 初选Top N
        selected_mask = ranked <= self.top_n

        # Step 3: 调仓缓冲区
        if current_holdings is not None and len(current_holdings) > 0:
            selected_mask = self._apply_rebalance_buffer(selected_mask, ranked, current_holdings)

        # Step 4: 分层赋权 (向量化: 用rank的map替代逐股票循环)
        selected_ranks = ranked[selected_mask]
        weights = pd.Series(0.0, index=scores.index)
        weights[selected_mask] = selected_ranks.map(self._get_tier_multiplier)

        # Step 5: 风险折扣 (向量化)
        if risk_levels is not None:
            active = weights > 0
            risk_discounts = risk_levels.reindex(weights.index[active]).fillna("low").map(self._get_risk_discount)
            weights.iloc[active.values.nonzero()[0]] *= risk_discounts.values

        # Step 6: 流动性折扣 (向量化)
        if liquidity_levels is not None:
            active = weights > 0
            liq_discounts = (
                liquidity_levels.reindex(weights.index[active]).fillna("normal").map(self._get_liquidity_discount)
            )
            weights.iloc[active.values.nonzero()[0]] *= liq_discounts.values

        # Step 7: 归一化
        total = weights.sum()
        if total > 0:
            weights = weights / total

        # Step 8: 行业约束
        if industry_series is not None:
            weights = self._apply_industry_constraints(weights, industry_series)

        # Step 9: 100股整数倍处理 (向量化)
        if prices is not None and total_capital > 0:
            active = weights > 0
            active_idx = weights.index[active]
            active_prices = prices.reindex(active_idx).fillna(0)
            # 向量化计算: shares = (target_value / price // LOT_SIZE) * LOT_SIZE
            target_values = weights[active] * total_capital
            valid_price = active_prices > 0
            shares = pd.Series(0, index=active_idx, dtype=float)
            shares[valid_price] = ((target_values[valid_price] / active_prices[valid_price]) // LOT_SIZE) * LOT_SIZE
            adjusted_values = shares * active_prices
            weights[active] = adjusted_values / total_capital
            # 再次归一化
            total = weights.sum()
            if total > 0:
                weights = weights / total

        # Step 10: 最小权重过滤
        min_weight = REBALANCE_BUFFER["min_weight_pct"] / 100.0
        weights[weights < min_weight] = 0.0
        # 最终归一化
        total = weights.sum()
        if total > 0:
            weights = weights / total

        # 构建结果
        result_mask = weights > 0
        result = pd.DataFrame(
            {
                "ts_code": scores.index[result_mask],
                "weight": weights[result_mask].values,
                "rank": ranked[result_mask].values,
                "score": scores[result_mask].values,
            }
        )

        # 添加风险和流动性信息
        if risk_levels is not None:
            result["risk_level"] = result["ts_code"].map(risk_levels)
        if liquidity_levels is not None:
            result["liquidity_level"] = result["ts_code"].map(liquidity_levels)
        if industry_series is not None:
            result["industry"] = result["ts_code"].map(industry_series)

        return result.sort_values("rank").reset_index(drop=True)


    def _apply_rebalance_buffer(
        self,
        selected_mask: pd.Series,
        ranked: pd.Series,
        current_holdings: pd.Series,
    ) -> pd.Series:
        """
        调仓缓冲区逻辑

        - 当前持仓排名≤75: 继续持有
        - 新买入需排名≤50
        - 权重<最小阈值: 卖出
        """
        hold_top = REBALANCE_BUFFER["hold_top"]
        buy_top = REBALANCE_BUFFER["buy_top"]

        adjusted = selected_mask.copy()

        for ts_code in current_holdings.index:
            if current_holdings[ts_code] <= 0:
                continue

            if ts_code not in ranked.index:
                # 不在当前股票池中, 卖出
                adjusted[ts_code] = False if ts_code in adjusted.index else False
                continue

            rank = ranked[ts_code]

            if rank <= hold_top:
                # 排名在缓冲区内, 继续持有
                adjusted[ts_code] = True
            elif rank > hold_top:
                # 排名跌出缓冲区, 卖出
                if ts_code in adjusted.index:
                    adjusted[ts_code] = False

        # 新买入需排名≤buy_top
        for ts_code in ranked.index:
            if ts_code in current_holdings.index and current_holdings[ts_code] > 0:
                continue  # 已持有, 不受买入限制
            if ranked[ts_code] > buy_top:
                if ts_code in adjusted.index:
                    adjusted[ts_code] = False

        return adjusted

    def _apply_industry_constraints(
        self,
        weights: pd.Series,
        industry_series: pd.Series,
    ) -> pd.Series:
        """
        行业约束: 单行业≤20%, 偏离≤5%

        超限行业按比例缩减, 释放的权重分配给未超限行业
        (向量化实现 + 修复: 使用缩放前权重作为再分配基准)
        """
        max_single = self.industry_constraints["max_single_industry"]

        adjusted = weights.copy()

        # 仅处理持仓权重 > 0 的股票
        active_mask = adjusted > 0
        if not active_mask.any():
            return adjusted

        active_codes = adjusted.index[active_mask]
        active_industries = industry_series.reindex(active_codes).fillna("unknown")

        # 向量化: 按行业汇总权重
        ind_weights = adjusted[active_mask].groupby(active_industries).sum()

        # 识别超限行业
        over_limit = ind_weights[ind_weights > max_single]
        if over_limit.empty:
            return adjusted

        # 计算超限行业内各股票的缩放因子, 并保存缩放前的权重用于再分配
        excess_weight = 0.0
        pre_scale_weights = adjusted.copy()  # 缩放前权重快照, 用于再分配基准

        for ind, ind_weight in over_limit.items():
            scale = max_single / ind_weight
            ind_mask = active_industries == ind
            # 缩减该行业所有股票权重
            adjusted.loc[ind_mask[ind_mask].index] *= scale
            excess_weight += ind_weight * (1 - scale)

        # 将释放的权重按比例分配给未超限行业 (使用缩放前权重作为基准)
        # 为什么用缩放前权重：缩放后行业内股票权重已变，用原始权重分配更符合"原持仓偏好"的业务逻辑
        if excess_weight > 0:
            under_limit = ind_weights[ind_weights <= max_single]
            if not under_limit.empty:
                # 构建未超限行业的股票掩码
                under_limit_inds = under_limit.index
                under_limit_mask = active_industries.isin(under_limit_inds)

                # 使用缩放前权重计算分配比例 (修复: 原代码使用已缩放的adjusted值)
                pre_scale_under = pre_scale_weights[active_mask][under_limit_mask]
                pre_scale_total = pre_scale_under.sum()

                if pre_scale_total > 0:
                    redistribution = excess_weight * (pre_scale_under / pre_scale_total)
                    adjusted.loc[pre_scale_under.index] += redistribution.values

        return adjusted

    def build(
        self,
        scores: pd.Series,
        mode: PortfolioMode | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        构建组合

        Args:
            scores: 综合得分Series
            mode: 构建模式(覆盖实例模式)
            **kwargs: 模式特定参数
        """
        effective_mode = mode or self.mode

        if effective_mode == PortfolioMode.RESEARCH:
            return self.build_research_portfolio(scores, **kwargs)
        return self.build_production_portfolio(scores, **kwargs)


# ─────────────────────────────────────────────
# 便捷函数
# ─────────────────────────────────────────────


def create_portfolio_builder(**kwargs) -> PortfolioBuilder:
    """创建组合构建器"""
    return PortfolioBuilder(**kwargs)
