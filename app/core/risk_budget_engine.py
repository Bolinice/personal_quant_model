"""
风险预算与择时引擎 V2
=====================
V2核心: 5信号4档仓位 + 回撤保护规则

5择时信号:
1. 指数中期趋势 (MA20>MA60:+1, MA60>MA120:+1)
2. 市场宽度 (上涨占比>60%:正面, 45%-60%:中性, <45%:负面)
3. 市场波动率 (低波动:正面, 中波动:中性, 高波动:负面)
4. 北向资金趋势 (20日净流入均值>0:+1, <0:-1)
5. 组合自身回撤 (回撤保护触发信号)

4档仓位映射:
- 强正面 → 100%
- 正面 → 80%
- 中性 → 60%
- 负面 → 30%

回撤保护(优先于择时):
- 回撤>5% → 降一档
- 回撤>8% → 再降一档
- 回撤>12% → 最低30%

保留原V1功能: 风险预算分配、实时风险分解、风险约束优化、尾部风险控制
"""
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
from datetime import date
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from app.core.logging import logger
from app.core.risk_model import RiskModel


class RiskAction(str, Enum):
    NORMAL = "normal"
    REDUCE_EXPOSURE = "reduce_exposure"
    INCREASE_HEDGE = "increase_hedge"
    FORCE_LIQUIDATE = "force_liquidate"


@dataclass
class RiskLimit:
    """风险限制配置"""
    max_portfolio_vol: float = 0.20       # 组合最大年化波动率
    max_factor_exposure: float = 1.0      # 单因子最大暴露
    max_industry_weight: float = 0.30     # 单行业最大权重
    max_single_position: float = 0.08     # 单股最大权重
    max_drawdown: float = 0.10            # 最大回撤
    var_limit_95: float = 0.02            # 95% VaR限制(日频)
    cvar_limit_95: float = 0.03          # 95% CVaR限制(日频)
    max_turnover: float = 0.30           # 单次最大换手率


class RiskBudgetEngine:
    """
    风险预算引擎
    核心理念: 风险是资源，应按预期收益分配，而非等权分配
    """

    def __init__(self, risk_model: Optional[RiskModel] = None,
                 risk_limits: Optional[RiskLimit] = None):
        self.risk_model = risk_model or RiskModel()
        self.risk_limits = risk_limits or RiskLimit()

    # ==================== 1. 风险预算分配 ====================

    def allocate_risk_budget(self,
                              factor_risk_contrib: Dict[str, float],
                              factor_icir: Dict[str, float],
                              target_total_risk: float = 0.15,
                              method: str = 'icir_proportional') -> Dict[str, float]:
        """
        风险预算分配
        将总风险预算按因子预期收益(ICIR)分配，而非等权

        Args:
            factor_risk_contrib: 各因子当前风险贡献 {factor: risk_pct}
            factor_icir: 各因子ICIR {factor: icir}
            target_total_risk: 目标总风险(年化波动率)
            method: 'icir_proportional' | 'equal' | 'risk_parity'
        """
        factors = list(set(factor_risk_contrib.keys()) & set(factor_icir.keys()))
        if not factors:
            return {}

        if method == 'equal':
            budget_per_factor = target_total_risk / len(factors)
            return {f: budget_per_factor for f in factors}

        elif method == 'icir_proportional':
            # ICIR正比分配: 高ICIR因子获得更多风险预算
            abs_icir = {f: max(abs(factor_icir.get(f, 0)), 0.01) for f in factors}
            total_icir = sum(abs_icir.values())
            if total_icir > 0:
                return {f: target_total_risk * abs_icir[f] / total_icir for f in factors}
            return {f: target_total_risk / len(factors) for f in factors}

        elif method == 'risk_parity':
            # 风险平价: 每个因子的风险贡献相等
            budget_per_factor = target_total_risk / len(factors)
            # 根据当前风险贡献调整: 高风险因子降权
            adjustments = {}
            for f in factors:
                current_risk = factor_risk_contrib.get(f, 1.0 / len(factors))
                if current_risk > 0:
                    adjustments[f] = budget_per_factor / current_risk
                else:
                    adjustments[f] = 1.0

            # 归一化
            total_adj = sum(adjustments.values())
            if total_adj > 0:
                return {f: target_total_risk * adjustments[f] / total_adj for f in factors}
            return {f: target_total_risk / len(factors) for f in factors}

        return {f: target_total_risk / len(factors) for f in factors}

    # ==================== 2. 实时风险分解 ====================

    def decompose_risk_realtime(self,
                                 portfolio_weights: pd.Series,
                                 factor_exposures: pd.DataFrame,
                                 factor_cov: pd.DataFrame,
                                 idiosyncratic_var: Optional[pd.Series] = None) -> Dict[str, Any]:
        """
        实时风险分解: 持仓级 → 因子级 → 行业级

        Args:
            portfolio_weights: 组合权重
            factor_exposures: 因子暴露度 (N x K)
            factor_cov: 因子协方差矩阵 (K x K)
            idiosyncratic_var: 特质方差 (N,)
        """
        common = portfolio_weights.index.intersection(factor_exposures.index)
        if len(common) == 0:
            return {}

        w = portfolio_weights.reindex(common).fillna(0).values
        X = factor_exposures.reindex(common).fillna(0).values
        F = factor_cov.reindex(
            factor_exposures.columns, factor_exposures.columns
        ).fillna(0).values

        # 组合因子暴露
        portfolio_exposure = w @ X  # (K,)

        # 因子风险贡献
        factor_risk = X @ F @ X.T  # (N, N)
        portfolio_var = w @ factor_risk @ w

        if portfolio_var <= 0:
            return {'total_vol': 0, 'factor_risk_pct': {}, 'idiosyncratic_risk_pct': 0}

        # 各因子风险贡献
        factor_contributions = {}
        for i, factor_name in enumerate(factor_exposures.columns):
            # 边际风险贡献: (X*F*X'*w)_i / sigma_p
            marginal = (X @ F)[:, i] @ w
            rc = w * marginal
            factor_contributions[factor_name] = float(rc.sum() / portfolio_var)

        # 特质风险
        idio_risk_pct = 0.0
        if idiosyncratic_var is not None:
            idio_var = idiosyncratic_var.reindex(common).fillna(0).values
            idio_risk = (w ** 2 * idio_var).sum()
            idio_risk_pct = idio_risk / (portfolio_var + idio_risk) if (portfolio_var + idio_risk) > 0 else 0

        total_vol = np.sqrt(portfolio_var) * np.sqrt(252)

        result = {
            'total_vol': round(total_vol, 4),
            'portfolio_var': round(portfolio_var, 6),
            'factor_exposure': {k: round(float(v), 4) for k, v in
                                zip(factor_exposures.columns, portfolio_exposure)},
            'factor_risk_pct': {k: round(v, 4) for k, v in factor_contributions.items()},
            'idiosyncratic_risk_pct': round(idio_risk_pct, 4),
            'factor_risk_total_pct': round(1 - idio_risk_pct, 4),
        }

        logger.info(
            "Real-time risk decomposition completed",
            extra={
                "total_vol": round(total_vol, 4),
                "n_factors": len(factor_exposures.columns),
                "idio_risk_pct": round(idio_risk_pct, 4),
            },
        )

        return result

    # ==================== 3. 风险约束优化 ====================

    def optimize_with_risk_constraints(self,
                                        alpha_signals: pd.Series,
                                        factor_exposures: pd.DataFrame,
                                        factor_cov: pd.DataFrame,
                                        risk_budget: Dict[str, float],
                                        idiosyncratic_var: Optional[pd.Series] = None,
                                        risk_aversion: float = 1.0,
                                        max_position: float = 0.08,
                                        long_only: bool = True) -> pd.Series:
        """
        风险约束组合优化
        max: w'*alpha - λ/2 * w'*Σ*w
        s.t.: 因子风险 ≤ 风险预算, 行业约束, 仓位约束

        Args:
            alpha_signals: alpha信号 (预期收益)
            factor_exposures: 因子暴露度
            factor_cov: 因子协方差矩阵
            risk_budget: 风险预算 {factor: budget}
            idiosyncratic_var: 特质方差
            risk_aversion: 风险厌恶系数
            max_position: 单股最大权重
            long_only: 是否仅做多
        """
        common = alpha_signals.index.intersection(factor_exposures.index)
        if len(common) < 2:
            return pd.Series(dtype=float)

        n = len(common)
        alpha = alpha_signals.reindex(common).fillna(0).values
        X = factor_exposures.reindex(common).fillna(0).values
        F = factor_cov.reindex(columns=factor_exposures.columns, index=factor_exposures.columns).fillna(0).values

        # 完整协方差: Σ = X*F*X' + D
        Sigma = X @ F @ X.T
        if idiosyncratic_var is not None:
            d = idiosyncratic_var.reindex(common).fillna(0).values
            Sigma += np.diag(np.maximum(d, 1e-10))
        Sigma = self.risk_model._ensure_positive_definite(Sigma)

        # 目标函数
        def objective(w):
            return -w @ alpha + risk_aversion / 2 * w @ Sigma @ w

        def gradient(w):
            return -alpha + risk_aversion * Sigma @ w

        # 约束
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]

        # 因子风险约束: |portfolio_exposure_k| <= budget_k
        # 用两个线性约束替代abs()非线性约束, 提升SLSQP收敛性
        for i, factor_name in enumerate(factor_exposures.columns):
            budget = risk_budget.get(factor_name, 0.5)
            constraints.append({
                'type': 'ineq',
                'fun': lambda w, idx=i, b=budget: b - w @ X[:, idx],
            })
            constraints.append({
                'type': 'ineq',
                'fun': lambda w, idx=i, b=budget: b + w @ X[:, idx],
            })

        # 权重边界
        if long_only:
            bounds = [(0, max_position) for _ in range(n)]
        else:
            bounds = [(-max_position, max_position) for _ in range(n)]

        # 初始值: 等权
        w0 = np.ones(n) / n

        result = minimize(
            objective, w0,
            method='SLSQP',
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 500, 'ftol': 1e-10},
        )

        if not result.success:
            logger.warning(f"Risk-constrained optimization: {result.message}")
            weights = pd.Series(1.0 / n, index=common)
        else:
            weights = pd.Series(result.x, index=common)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== 4. 尾部风险控制 ====================

    def adjust_for_tail_risk(self,
                              weights: pd.Series,
                              returns: pd.DataFrame,
                              cvar_limit: float = 0.03,
                              confidence: float = 0.95,
                              dcc_garch_cov: Optional[pd.DataFrame] = None) -> pd.Series:
        """
        尾部风险调整
        当组合CVaR超过限制时，自动缩减高风险资产权重

        Args:
            weights: 当前权重
            returns: 历史收益率矩阵
            cvar_limit: CVaR限制(日频)
            confidence: 置信水平
            dcc_garch_cov: DCC-GARCH协方差矩阵(可选)
        """
        if weights.empty or returns.empty:
            return weights

        # 计算当前组合CVaR
        common = weights.index.intersection(returns.columns)
        if len(common) < 2:
            return weights

        w = weights.reindex(common).fillna(0).values
        R = returns[common].values

        # 组合收益率
        port_returns = R @ w

        # 计算CVaR
        var_threshold = np.percentile(port_returns, (1 - confidence) * 100)
        tail_returns = port_returns[port_returns <= var_threshold]
        cvar = -tail_returns.mean() if len(tail_returns) > 0 else 0

        if cvar <= cvar_limit:
            return weights  # CVaR在限制内

        # CVaR超标: 缩减高Beta资产权重
        # 计算各资产对CVaR的贡献
        asset_cvar_contrib = np.zeros(len(common))
        for i in range(len(common)):
            # 单资产CVaR贡献 ≈ w_i * β_i * CVaR_market
            asset_returns = R[:, i]
            if port_returns.std() > 0 and asset_returns.std() > 0:
                beta = np.cov(asset_returns, port_returns)[0, 1] / port_returns.var()
            else:
                beta = 1.0
            asset_cvar_contrib[i] = w[i] * beta * cvar

        # 按CVaR贡献缩减
        total_contrib = asset_cvar_contrib.sum()
        if total_contrib > 0:
            # 缩减比例: 使CVaR回到限制内
            shrinkage = min(0.5, (cvar - cvar_limit) / cvar)
            adjusted_w = w.copy()
            for i in range(len(common)):
                if asset_cvar_contrib[i] > 0:
                    # 高贡献资产缩减更多
                    asset_shrinkage = shrinkage * (asset_cvar_contrib[i] / total_contrib)
                    adjusted_w[i] *= (1 - asset_shrinkage)

            # 归一化
            if adjusted_w.sum() > 0:
                adjusted_w = adjusted_w / adjusted_w.sum()

            adjusted = pd.Series(adjusted_w, index=common)
            logger.info(
                "Tail risk adjustment applied",
                extra={
                    "original_cvar": round(cvar, 6),
                    "cvar_limit": cvar_limit,
                    "shrinkage": round(shrinkage, 4),
                },
            )
            return adjusted

        return weights

    # ==================== 5. 风险信号反馈 ====================

    def check_risk_limits(self,
                           current_risk: Dict[str, float],
                           risk_limits: Optional[RiskLimit] = None) -> RiskAction:
        """
        检查风险限制并返回操作信号

        Args:
            current_risk: 当前风险指标 {
                'portfolio_vol', 'max_drawdown', 'var_95', 'cvar_95',
                'max_factor_exposure', 'max_industry_weight'
            }
            risk_limits: 风险限制(默认使用self.risk_limits)
        """
        limits = risk_limits or self.risk_limits
        violations = []

        # 波动率检查
        vol = current_risk.get('portfolio_vol', 0)
        if vol > limits.max_portfolio_vol:
            violations.append('portfolio_vol')

        # 回撤检查
        dd = abs(current_risk.get('max_drawdown', 0))
        if dd > limits.max_drawdown:
            violations.append('max_drawdown')

        # VaR检查
        var = abs(current_risk.get('var_95', 0))
        if var > limits.var_limit_95:
            violations.append('var_95')

        # CVaR检查
        cvar = abs(current_risk.get('cvar_95', 0))
        if cvar > limits.cvar_limit_95:
            violations.append('cvar_95')

        # 因子暴露检查
        max_fe = current_risk.get('max_factor_exposure', 0)
        if abs(max_fe) > limits.max_factor_exposure:
            violations.append('max_factor_exposure')

        # 决策
        if len(violations) >= 3:
            action = RiskAction.FORCE_LIQUIDATE
        elif 'max_drawdown' in violations or 'cvar_95' in violations:
            action = RiskAction.REDUCE_EXPOSURE
        elif len(violations) > 0:
            action = RiskAction.INCREASE_HEDGE
        else:
            action = RiskAction.NORMAL

        if action != RiskAction.NORMAL:
            logger.warning(
                "Risk limit violation detected",
                extra={
                    "action": action.value,
                    "violations": violations,
                    "current_risk": {k: round(v, 4) for k, v in current_risk.items()},
                },
            )

        return action

    def compute_risk_adjusted_exposure(self, action: RiskAction,
                                        base_exposure: float = 1.0) -> float:
        """根据风险信号计算调整后的仓位"""
        if action == RiskAction.NORMAL:
            return base_exposure
        elif action == RiskAction.REDUCE_EXPOSURE:
            return base_exposure * 0.5
        elif action == RiskAction.INCREASE_HEDGE:
            return base_exposure * 0.7
        elif action == RiskAction.FORCE_LIQUIDATE:
            return base_exposure * 0.2
        return base_exposure

    # ==================== 6. 组合风险报告 ====================

    def generate_risk_report(self,
                              portfolio_weights: pd.Series,
                              factor_exposures: pd.DataFrame,
                              factor_cov: pd.DataFrame,
                              returns: pd.DataFrame,
                              industry_data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        生成完整风险报告
        """
        # 风险分解
        decomposition = self.decompose_risk_realtime(
            portfolio_weights, factor_exposures, factor_cov
        )

        # VaR/CVaR
        common = portfolio_weights.index.intersection(returns.columns)
        if len(common) > 0:
            w = portfolio_weights.reindex(common).fillna(0).values
            port_returns = returns[common].values @ w

            var_95 = -np.percentile(port_returns, 5)
            cvar_95 = -port_returns[port_returns <= -var_95].mean() if (port_returns <= -var_95).any() else var_95
        else:
            var_95 = 0
            cvar_95 = 0

        # 行业集中度
        industry_concentration = {}
        if industry_data:
            for ts_code, weight in portfolio_weights.items():
                industry = industry_data.get(ts_code, 'Unknown')
                industry_concentration[industry] = industry_concentration.get(industry, 0) + weight

        # 风险检查
        risk_metrics = {
            'portfolio_vol': decomposition.get('total_vol', 0),
            'max_drawdown': 0,  # 需要外部传入
            'var_95': var_95,
            'cvar_95': cvar_95,
            'max_factor_exposure': max(
                abs(v) for v in decomposition.get('factor_exposure', {}).values()
            ) if decomposition.get('factor_exposure') else 0,
            'max_industry_weight': max(industry_concentration.values()) if industry_concentration else 0,
        }

        action = self.check_risk_limits(risk_metrics)

        return {
            'risk_decomposition': decomposition,
            'var_95': round(var_95, 6),
            'cvar_95': round(cvar_95, 6),
            'industry_concentration': {k: round(v, 4) for k, v in industry_concentration.items()},
            'risk_action': action.value,
            'risk_metrics': {k: round(v, 6) for k, v in risk_metrics.items()},
        }

    # ==================== V2: 5信号4档择时 ====================

    # 4档仓位映射
    POSITION_TIERS = {
        'strong_positive': 1.00,   # 强正面 → 100%
        'positive': 0.80,          # 正面 → 80%
        'neutral': 0.60,           # 中性 → 60%
        'negative': 0.30,          # 负面 → 30%
    }

    # 回撤保护阈值
    DRAWDOWN_THRESHOLDS = {
        'level1': 0.05,   # >5% 降一档
        'level2': 0.08,   # >8% 再降一档
        'level3': 0.12,   # >12% 最低30%
    }

    def timing_signal_trend(self, index_data: pd.DataFrame,
                            price_col: str = 'close') -> int:
        """
        信号1: 指数中期趋势

        - MA20 > MA60: +1
        - MA60 > MA120: +1
        - 否则: 0
        得分范围: 0~2
        """
        if index_data.empty or price_col not in index_data.columns:
            return 0

        close = index_data[price_col].values
        if len(close) < 120:
            if len(close) >= 60:
                ma20 = np.mean(close[-20:])
                ma60 = np.mean(close[-60:])
                return 1 if ma20 > ma60 else 0
            return 0

        ma20 = np.mean(close[-20:])
        ma60 = np.mean(close[-60:])
        ma120 = np.mean(close[-120:])

        score = 0
        if ma20 > ma60:
            score += 1
        if ma60 > ma120:
            score += 1
        return score

    def timing_signal_breadth(self, stock_data: pd.DataFrame,
                                pct_col: str = 'pct_chg') -> int:
        """
        信号2: 市场宽度

        - 上涨占比 > 60%: +1 (正面)
        - 45% ~ 60%: 0 (中性)
        - < 45%: -1 (负面)
        """
        if stock_data.empty or pct_col not in stock_data.columns:
            return 0

        pct = stock_data[pct_col].dropna()
        if len(pct) < 100:
            return 0

        up_ratio = (pct > 0).mean()
        if up_ratio > 0.60:
            return 1
        elif up_ratio < 0.45:
            return -1
        return 0

    def timing_signal_volatility(self, index_data: pd.DataFrame,
                                  price_col: str = 'close',
                                  window: int = 60) -> int:
        """
        信号3: 市场波动率

        - 低波动(<25%分位): +1 (正面)
        - 中波动(25%~75%分位): 0 (中性)
        - 高波动(>75%分位): -1 (负面)
        """
        if index_data.empty or price_col not in index_data.columns:
            return 0

        returns = index_data[price_col].pct_change().dropna()
        if len(returns) < window:
            return 0

        recent_vol = returns.tail(20).std() * np.sqrt(252)
        hist_vol = returns.tail(window).std() * np.sqrt(252)

        # 分位数判断
        vol_series = returns.rolling(20).std().dropna() * np.sqrt(252)
        if len(vol_series) < 60:
            return 0

        q25 = vol_series.quantile(0.25)
        q75 = vol_series.quantile(0.75)

        if recent_vol < q25:
            return 1
        elif recent_vol > q75:
            return -1
        return 0

    def timing_signal_northbound(self, northbound_data: pd.DataFrame,
                                  amount_col: str = 'net_amount',
                                  date_col: str = 'trade_date',
                                  window: int = 20) -> int:
        """
        信号4: 北向资金趋势

        - 近20日净流入均值显著为正: +1
        - 显著为负: -1
        - 否则: 0
        """
        if northbound_data.empty:
            return 0

        if date_col in northbound_data.columns and amount_col in northbound_data.columns:
            recent = northbound_data.sort_values(date_col).tail(window)
            if len(recent) < 10:
                return 0
            mean_flow = recent[amount_col].mean()
            std_flow = recent[amount_col].std()
            if std_flow > 0 and abs(mean_flow) > 0.5 * std_flow:
                return 1 if mean_flow > 0 else -1
        return 0

    def timing_signal_drawdown(self, current_drawdown: float) -> int:
        """
        信号5: 组合自身回撤 (回撤保护触发信号)

        回撤保护规则(优先于择时):
        - 回撤 > 5%: 降一档
        - 回撤 > 8%: 再降一档
        - 回撤 > 12%: 最低30%

        Args:
            current_drawdown: 当前回撤(负数, 如-0.06表示6%回撤)

        Returns:
            降档数 (0/1/2/3)
        """
        dd = abs(current_drawdown)
        if dd > self.DRAWDOWN_THRESHOLDS['level3']:
            return 3  # 最低30%
        elif dd > self.DRAWDOWN_THRESHOLDS['level2']:
            return 2  # 再降一档
        elif dd > self.DRAWDOWN_THRESHOLDS['level1']:
            return 1  # 降一档
        return 0

    def compute_timing_position(
        self,
        index_data: pd.DataFrame = None,
        stock_data: pd.DataFrame = None,
        northbound_data: pd.DataFrame = None,
        current_drawdown: float = 0.0,
        price_col: str = 'close',
        pct_col: str = 'pct_chg',
    ) -> Dict[str, Any]:
        """
        V2: 5信号4档仓位计算

        Returns:
            {
                'position': float,          # 目标仓位 (0.30~1.00)
                'tier': str,                # 仓位档位
                'signals': Dict[str, int],   # 各信号得分
                'drawdown_protection': Dict, # 回撤保护信息
            }
        """
        # 计算各信号
        signals = {}

        # 信号1: 指数中期趋势 (0~2)
        if index_data is not None and not index_data.empty:
            signals['trend'] = self.timing_signal_trend(index_data, price_col)
        else:
            signals['trend'] = 0

        # 信号2: 市场宽度 (-1~+1)
        if stock_data is not None and not stock_data.empty:
            signals['breadth'] = self.timing_signal_breadth(stock_data, pct_col)
        else:
            signals['breadth'] = 0

        # 信号3: 市场波动率 (-1~+1)
        if index_data is not None and not index_data.empty:
            signals['volatility'] = self.timing_signal_volatility(index_data, price_col)
        else:
            signals['volatility'] = 0

        # 信号4: 北向资金趋势 (-1~+1)
        if northbound_data is not None and not northbound_data.empty:
            signals['northbound'] = self.timing_signal_northbound(northbound_data)
        else:
            signals['northbound'] = 0

        # 综合信号得分
        total_score = sum(signals.values())

        # 映射到4档仓位
        if total_score >= 3:
            tier = 'strong_positive'
        elif total_score >= 1:
            tier = 'positive'
        elif total_score >= -1:
            tier = 'neutral'
        else:
            tier = 'negative'

        position = self.POSITION_TIERS[tier]

        # 回撤保护(优先于择时)
        drawdown_drops = self.timing_signal_drawdown(current_drawdown)
        drawdown_info = {
            'current_drawdown': round(current_drawdown, 4),
            'drawdown_drops': drawdown_drops,
            'protection_active': drawdown_drops > 0,
        }

        if drawdown_drops > 0:
            # 按降档数降低仓位
            tier_list = ['strong_positive', 'positive', 'neutral', 'negative']
            current_idx = tier_list.index(tier)
            new_idx = min(current_idx + drawdown_drops, len(tier_list) - 1)
            tier = tier_list[new_idx]
            position = self.POSITION_TIERS[tier]
            drawdown_info['original_tier'] = tier_list[current_idx]
            drawdown_info['adjusted_tier'] = tier

        result = {
            'position': position,
            'tier': tier,
            'signals': signals,
            'total_score': total_score,
            'drawdown_protection': drawdown_info,
        }

        logger.info(
            "V2 timing position computed",
            extra={
                "position": position,
                "tier": tier,
                "signals": signals,
                "total_score": total_score,
                "drawdown_drops": drawdown_drops,
            },
        )

        return result