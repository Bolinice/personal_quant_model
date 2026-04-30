"""
组合优化器 - 统一优化入口
均值方差优化、风险平价、最小方差、最大去相关、Black-Litterman、
Mean-CVaR、HRP层次风险平价、稳健优化、交易成本感知优化、
Alpha-Risk优化(GPT设计10.1节)、分数映射权重(GPT设计10.3节)
"""

from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.core.logging import logger


class PortfolioOptimizer:
    """组合优化器 - 含A股实盘约束"""

    def __init__(self):
        pass

    # ==================== A股实盘约束过滤 ====================

    @staticmethod
    def filter_ashare_constraints(
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        stock_status: dict[str, dict] | None = None,
        exclude_st: bool = True,
        exclude_new_ipo_days: int = 60,  # A股新股上市初期波动剧烈且缺乏历史数据，60天过滤期兼顾数据充分性与覆盖面
        exclude_limit_up: bool = True,  # 涨停股无法买入，纳入优化会导致不可执行权重
        min_daily_volume: float = 0,
        current_date: Any | None = None,
    ) -> tuple[pd.Series, pd.DataFrame]:
        """
        A股实盘约束过滤: 在优化前排除不符合交易条件的股票

        Args:
            expected_returns: 期望收益
            cov_matrix: 协方差矩阵
            stock_status: 股票状态 {ts_code: {is_st, list_date, is_limit_up, is_suspended, ...}}
            exclude_st: 是否排除ST股
            exclude_new_ipo_days: 排除上市不足N天的新股
            exclude_limit_up: 是否排除涨停股
            min_daily_volume: 最低日均成交额(元)
            current_date: 当前日期(用于计算IPO天数)

        Returns:
            (过滤后的期望收益, 过滤后的协方差矩阵)
        """
        if stock_status is None:
            return expected_returns, cov_matrix

        common = expected_returns.index.intersection(cov_matrix.index)
        excluded = set()

        for ts_code in common:
            status = stock_status.get(ts_code, {})

            # 排除ST股
            if exclude_st and status.get("is_st", False):
                excluded.add(ts_code)

            # 排除新股
            if exclude_new_ipo_days > 0 and current_date is not None:
                list_date = status.get("list_date")
                if list_date is not None:
                    from datetime import date as date_type

                    if isinstance(list_date, str):
                        list_date = pd.Timestamp(list_date).date()
                    if isinstance(current_date, date_type):
                        days_since_ipo = (current_date - list_date).days
                    else:
                        days_since_ipo = (pd.Timestamp(current_date).date() - list_date).days
                    if days_since_ipo < exclude_new_ipo_days:
                        excluded.add(ts_code)

            # 排除涨停股
            if exclude_limit_up and status.get("is_limit_up", False):
                excluded.add(ts_code)

            # 排除停牌股
            if status.get("is_suspended", False):
                excluded.add(ts_code)

            # 排除低流动性股
            if min_daily_volume > 0:
                daily_vol = status.get("daily_volume", 0)
                if daily_vol < min_daily_volume:
                    excluded.add(ts_code)

        valid = [c for c in common if c not in excluded]
        if len(valid) < 2:  # 少于2只资产无法构建有效组合
            logger.warning(f"Too few assets after constraint filtering: {len(valid)}")
            return expected_returns, cov_matrix

        if excluded:
            logger.info(f"A-share constraints excluded {len(excluded)} stocks, {len(valid)} remaining")

        return expected_returns.reindex(valid), cov_matrix.loc[valid, valid]

    # ==================== 均值方差优化 ====================

    def mean_variance_optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        risk_aversion: float = 1.0,  # λ=1对应中等风险偏好，A股增强策略通常0.5~2.0
        max_position: float = 0.10,  # 10%个股权重上限，防止单票过度集中
        min_position: float = 0.0,
        industry_data: pd.Series = None,
        max_industry_weight: float = 0.30,  # 单行业30%上限，对标沪深300行业权重分散度
        long_only: bool = True,
    ) -> pd.Series:
        """
        均值方差优化

        max: w'μ - λ/2 * w'Σw
        s.t.: w'1 = 1, w >= 0

        Args:
            expected_returns: 期望收益, index=ts_code
            cov_matrix: 协方差矩阵
            risk_aversion: 风险厌恶系数 λ
            max_position: 单只股票最大权重
            min_position: 单只股票最小权重
            industry_data: 行业数据
            max_industry_weight: 单个行业最大权重
            long_only: 是否仅做多

        Returns:
            最优权重 Series
        """
        # 对齐数据
        common = expected_returns.index.intersection(cov_matrix.index)
        n = len(common)

        if n < 2:
            logger.warning("Too few assets for optimization")
            return pd.Series(1.0 / n, index=common) if n > 0 else pd.Series()

        mu = expected_returns.reindex(common).values
        Sigma = cov_matrix.loc[common, common].values
        Sigma = self._ensure_positive_definite(Sigma)

        # 目标函数: min -w'μ + λ/2 * w'Σw  (最大化效用U = E[R] - λ/2 * Var，取负号转最小化)
        def objective(w):
            return -w @ mu + risk_aversion / 2 * w @ Sigma @ w

        def gradient(w):
            return -mu + risk_aversion * Sigma @ w

        # 约束: 权重之和=1 (全仓约束)
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # 权重边界: A股融券限制大，long_only为默认；max_position防止单票过度集中
        if long_only:
            bounds = [(min_position, max_position) for _ in range(n)]
        else:
            bounds = [(-max_position, max_position) for _ in range(n)]

        # 行业约束: 硬约束确保不因优化器贪心而过度偏离行业中性
        if industry_data is not None:
            ind = industry_data.reindex(common)
            for industry in ind.unique():
                if pd.isna(industry):
                    continue
                idx = np.where(ind.values == industry)[0]
                if len(idx) > 0:
                    constraints.append({"type": "ineq", "fun": lambda w, idx=idx: max_industry_weight - np.sum(w[idx])})

        # 初始值: 等权 (凸优化下等权是安全起点)
        w0 = np.ones(n) / n

        # SLSQP适合中小规模凸优化(50~300只)，大规模需换ADMM类求解器
        result = minimize(
            objective,
            w0,
            method="SLSQP",
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-10},
        )

        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")
            # 回退到等权 (优化不收敛时等权是最安全的默认，不依赖任何输入假设)
            weights = pd.Series(1.0 / n, index=common)
        else:
            weights = pd.Series(result.x, index=common)
            # 清理微小权重 (低于0.01%视为数值噪声，清零避免无效持仓)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return self._filter_min_holding(weights)

    @staticmethod
    def _filter_min_holding(
        weights: pd.Series, min_holding_value: float = 0.001
    ) -> pd.Series:  # 0.1%≈100万资金下1000元，约1手A股
        """过滤不足最小持仓的权重 (A股最小交易单位100股)
        如果权重对应的金额不足一手，清零后重新归一化

        Args:
            weights: 优化后的权重
            min_holding_value: 最小持仓权重 (如0.001=0.1%，对应100万资金下1000元≈1手)
        """
        if min_holding_value <= 0:
            return weights
        # 清零不足最小持仓的权重
        weights = weights.copy()
        weights[weights < min_holding_value] = 0
        if weights.sum() > 0:
            weights = weights / weights.sum()
        return weights

    # ==================== 分数映射权重 (GPT设计10.3方法B) ====================

    def score_to_weight(
        self,
        scores: pd.Series,
        industry_data: pd.Series | None = None,
        max_position: float = 0.03,  # 增强策略个股权重更严格(3% vs 均值方差的10%)，控制跟踪误差
        max_industry_weight: float = 0.30,
        benchmark_weights: pd.Series | None = None,
        max_industry_dev: float = 0.03,
    ) -> pd.Series:  # 行业偏离3%对标增强指数常见约束，过大则失去行业中性
        """
        分数映射权重 (GPT设计10.3方法B)
        w_i ∝ max(0, S_i), 然后约束单票和行业

        比Top-N排序更优: 保留分数信息, 避免硬切换

        Args:
            scores: alpha分数, index=ts_code
            industry_data: 行业映射, index=ts_code
            max_position: 单票最大权重
            max_industry_weight: 单行业最大权重
            benchmark_weights: 基准权重 (用于行业偏离约束)
            max_industry_dev: 相对基准的最大行业偏离

        Returns:
            目标权重 Series
        """
        # 正分数映射: 只做多正分数股票 (负分意味着alpha预期为负，做空受A股融券限制)
        positive = scores.clip(lower=0)
        if positive.sum() == 0:
            # 全部非正, 回退到等权 (无有效alpha信号时，等权是最小假设的组合)
            n = len(scores)
            return pd.Series(1.0 / n, index=scores.index) if n > 0 else pd.Series()

        # 归一化
        weights = positive / positive.sum()

        # 单票约束
        weights = weights.clip(upper=max_position)
        if weights.sum() > 0:
            weights = weights / weights.sum()

        # 行业约束: 控制行业权重偏离，防止单行业过度集中
        if industry_data is not None:
            # 计算行业权重
            industry_w = {}
            for ts_code, w in weights.items():
                if w > 0:
                    ind = industry_data.get(ts_code, "unknown")
                    industry_w[ind] = industry_w.get(ind, 0) + w

            # 基准行业权重 (如果有)
            bench_ind_w = {}
            if benchmark_weights is not None:
                for ts_code, bw in benchmark_weights.items():
                    if bw > 0:
                        ind = industry_data.get(ts_code, "unknown")
                        bench_ind_w[ind] = bench_ind_w.get(ind, 0) + bw

            # 超限行业缩放: 同行业内等比例缩减，而非删除个股，保持行业内相对排序
            for ind, total_w in industry_w.items():
                if benchmark_weights is not None and ind in bench_ind_w:
                    limit = bench_ind_w[ind] + max_industry_dev
                else:
                    limit = max_industry_weight

                if total_w > limit:
                    scale = limit / total_w
                    for ts_code in weights.index:
                        if industry_data.get(ts_code) == ind and weights[ts_code] > 0:
                            weights[ts_code] *= scale

            # 重新归一化
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return self._filter_min_holding(weights)

    # ==================== Alpha-Risk完整优化 (GPT设计10.1节) ====================

    def alpha_risk_optimize(
        self,
        alpha_scores: pd.Series,
        risk_model_cov: pd.DataFrame,
        current_weights: pd.Series | None = None,
        industry_data: pd.Series | None = None,
        style_exposures: pd.DataFrame | None = None,
        style_bounds: dict[str, tuple[float, float]] | None = None,
        benchmark_industry_weights: dict[str, float] | None = None,
        risk_aversion: float = 1.0,
        turnover_penalty: float = 0.003,  # 30bps换手成本，近似A股双边佣金+滑点+印花税
        max_position: float = 0.03,  # 增强策略3%上限，对应约33只等权持仓
        max_industry_dev: float = 0.03,  # 行业偏离3%硬约束，控制主动行业暴露
        long_only: bool = True,
    ) -> pd.Series:
        """
        完整alpha-risk优化 (GPT设计10.1节)

        max: α'w - λ/2 * w'Σw - γ||w-w_prev||_1 - η*ExposurePenalty
        s.t. 行业偏离<=3%, 单票<=3%, 风格暴露约束, 流动性约束

        Args:
            alpha_scores: alpha分数, index=ts_code
            risk_model_cov: 风险模型协方差矩阵
            current_weights: 当前持仓权重 (用于换手惩罚)
            industry_data: 行业映射, index=ts_code
            style_exposures: 风格暴露, index=ts_code, columns=风格因子名
            style_bounds: 风格暴露约束 {factor: (lower, upper)}
            benchmark_industry_weights: 基准行业权重 {industry: weight}
            risk_aversion: 风险厌恶系数 λ
            turnover_penalty: 换手惩罚系数 γ
            max_position: 单票最大权重
            max_industry_dev: 最大行业偏离(相对基准)
            long_only: 是否仅做多

        Returns:
            最优权重 Series
        """
        common = alpha_scores.index.intersection(risk_model_cov.index)
        n = len(common)
        if n < 2:
            return pd.Series(1.0 / n, index=common) if n > 0 else pd.Series()

        alpha = alpha_scores.reindex(common).values
        Sigma = risk_model_cov.loc[common, common].values
        Sigma = self._ensure_positive_definite(Sigma)
        w_prev = current_weights.reindex(common).fillna(0).values if current_weights is not None else np.zeros(n)

        # 尝试使用cvxpy (支持L1换手惩罚，SLSQP原生不支持L1范数)
        try:
            import cvxpy as cp

            w = cp.Variable(n)
            dw = w - w_prev

            # 目标: max α'w - λ/2 * w'Σw - γ||dw||_1
            # 三项分别：alpha收益(拉高权重) - 风险惩罚(分散化) - 换手成本(抑制过度交易)
            obj = alpha @ w - risk_aversion / 2 * cp.quad_form(w, Sigma)
            if turnover_penalty > 0:
                obj -= turnover_penalty * cp.norm1(dw)

            objective = cp.Maximize(obj)
            constraints = [cp.sum(w) == 1]

            if long_only:
                constraints.append(w >= 0)
            constraints.append(w <= max_position)

            # 行业偏离约束: 双向硬约束(|w_ind - bench_ind| <= max_dev)
            # 硬约束而非惩罚项，防止优化器在alpha强信号下突破行业偏离上限
            if industry_data is not None and benchmark_industry_weights is not None:
                ind = industry_data.reindex(common)
                for industry in ind.unique():
                    if pd.isna(industry) or industry not in benchmark_industry_weights:
                        continue
                    idx = np.where(ind.values == industry)[0]
                    bench_w = benchmark_industry_weights[industry]
                    if len(idx) > 0:
                        # 行业权重 - 基准 <= max_dev (超配上限)
                        constraints.append(cp.sum(w[idx]) - bench_w <= max_industry_dev)
                        # 基准 - 行业权重 <= max_dev (低配上限)
                        constraints.append(bench_w - cp.sum(w[idx]) <= max_industry_dev)

            # 风格暴露约束: 限制规模/价值/动量等风格暴露，避免隐性风格赌博
            if style_exposures is not None and style_bounds is not None:
                X = style_exposures.reindex(common).fillna(0)
                for factor_name, (lo, hi) in style_bounds.items():
                    if factor_name in X.columns:
                        exposure = X[factor_name].values
                        constraints.append(exposure @ w >= lo)
                        constraints.append(exposure @ w <= hi)

            problem = cp.Problem(objective, constraints)
            try:
                problem.solve(solver=cp.SCS, max_iters=2000)  # SCS处理二阶锥问题更稳定
            except cp.SolverError:
                problem.solve(solver=cp.ECOS, max_iters=500)  # ECOS作为备选，对中小规模更快

            if problem.status in ["optimal", "optimal_inaccurate"] and w.value is not None:
                # 投影到非负: 求解器可能产生极小负值(数值误差)，截断处理
                weights = np.maximum(w.value, 0)
                if weights.sum() > 0:
                    weights = weights / weights.sum()
                return self._filter_min_holding(pd.Series(weights, index=common))

        except ImportError:
            pass

        # 回退: 使用SLSQP (不支持L1, 用L2近似换手惩罚，牺牲稀疏性换取可解性)
        def objective(w):
            alpha_term = -alpha @ w
            risk_term = risk_aversion / 2 * w @ Sigma @ w
            turnover_term = turnover_penalty * np.sum((w - w_prev) ** 2)  # L2近似: 不产生稀疏换手，但保证凸性和可微性
            return alpha_term + risk_term + turnover_term

        def gradient(w):
            return -alpha + risk_aversion * Sigma @ w + 2 * turnover_penalty * (w - w_prev)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = (
            [(0, max_position) for _ in range(n)] if long_only else [(-max_position, max_position) for _ in range(n)]
        )

        # 行业偏离约束 (SLSQP回退路径，与cvxpy路径逻辑相同)
        if industry_data is not None and benchmark_industry_weights is not None:
            ind = industry_data.reindex(common)
            for industry in ind.unique():
                if pd.isna(industry) or industry not in benchmark_industry_weights:
                    continue
                idx = np.where(ind.values == industry)[0]
                bench_w = benchmark_industry_weights[industry]
                if len(idx) > 0:
                    constraints.append(
                        {"type": "ineq", "fun": lambda w, idx=idx, bw=bench_w: max_industry_dev - (np.sum(w[idx]) - bw)}
                    )
                    constraints.append(
                        {"type": "ineq", "fun": lambda w, idx=idx, bw=bench_w: max_industry_dev - (bw - np.sum(w[idx]))}
                    )

        w0 = np.ones(n) / n
        result = minimize(
            objective,
            w0,
            method="SLSQP",
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-10},
        )

        if result.success:
            weights = pd.Series(result.x, index=common)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()
        else:
            logger.warning(f"Alpha-risk optimization did not converge: {result.message}")
            # 优化失败回退到分数映射(更鲁棒的无优化方法)
            weights = self.score_to_weight(alpha_scores, industry_data, max_position)

        return self._filter_min_holding(weights)

    # ==================== 风险平价优化 ====================

    def risk_parity_optimize(
        self, cov_matrix: pd.DataFrame, max_position: float = 0.10, target_risk: pd.Series | None = None
    ) -> pd.Series:
        """
        风险平价优化

        每个资产的风险贡献相等: w_i * (Σw)_i / (w'Σw) = 1/N

        Args:
            cov_matrix: 协方差矩阵
            max_position: 单只股票最大权重
            target_risk: 目标风险比例, 默认等风险贡献

        Returns:
            最优权重 Series
        """
        stocks = cov_matrix.index
        n = len(stocks)
        Sigma = cov_matrix.values
        Sigma = self._ensure_positive_definite(Sigma)

        if target_risk is None:
            target_risk = np.ones(n) / n
        else:
            target_risk = target_risk.reindex(stocks).values
            target_risk = target_risk / target_risk.sum()

        # 目标函数: 最小化风险贡献与目标的偏差 (等风险贡献时target=1/N)
        # 风险平价让每项资产对组合风险的贡献相等，避免高波动资产主导风险
        def objective(w):
            port_var = w @ Sigma @ w
            if port_var <= 0:
                return 1e10  # 无效组合返回大罚值，驱使优化器远离退化解
            mrc = Sigma @ w  # 边际风险贡献 (∂σ_p/∂w_i)
            rc = w * mrc  # 风险贡献
            rc_pct = rc / port_var  # 风险贡献占比
            return np.sum((rc_pct - target_risk) ** 2)

        # 约束
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0, max_position) for _ in range(n)]

        # 初始值: 按波动率倒数加权 (风险平价的解析近似，加速收敛)
        vols = np.sqrt(np.diag(Sigma))
        inv_vol = 1.0 / vols
        w0 = inv_vol / inv_vol.sum()

        result = minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-12},
        )

        if not result.success:
            logger.warning(f"Risk parity optimization did not converge: {result.message}")
            weights = pd.Series(w0, index=stocks)
        else:
            weights = pd.Series(result.x, index=stocks)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== 最小方差组合 ====================

    def min_variance_optimize(
        self,
        cov_matrix: pd.DataFrame,
        max_position: float = 0.10,
        industry_data: pd.Series = None,
        max_industry_weight: float = 0.30,
    ) -> pd.Series:
        """
        最小方差组合

        min: w'Σw
        s.t.: w'1 = 1, w >= 0

        Args:
            cov_matrix: 协方差矩阵
            max_position: 单只股票最大权重
            industry_data: 行业数据
            max_industry_weight: 单个行业最大权重

        Returns:
            最优权重 Series
        """
        stocks = cov_matrix.index
        n = len(stocks)
        Sigma = cov_matrix.values
        Sigma = self._ensure_positive_definite(Sigma)

        def objective(w):
            return w @ Sigma @ w

        def gradient(w):
            return 2 * Sigma @ w

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0, max_position) for _ in range(n)]

        # 行业约束: 防止最小方差组合过度集中在低波动行业(如银行/公用事业)
        if industry_data is not None:
            ind = industry_data.reindex(stocks)
            for industry in ind.unique():
                if pd.isna(industry):
                    continue
                idx = np.where(ind.values == industry)[0]
                if len(idx) > 0:
                    constraints.append({"type": "ineq", "fun": lambda w, idx=idx: max_industry_weight - np.sum(w[idx])})

        w0 = np.ones(n) / n

        result = minimize(
            objective,
            w0,
            method="SLSQP",
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-10},
        )

        if not result.success:
            logger.warning(f"Min variance optimization did not converge: {result.message}")
            weights = pd.Series(1.0 / n, index=stocks)
        else:
            weights = pd.Series(result.x, index=stocks)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== 最大去相关组合 ====================

    def max_decorrelation_optimize(self, cov_matrix: pd.DataFrame, max_position: float = 0.10) -> pd.Series:
        """
        最大去相关组合

        最小化组合内资产间的平均相关系数

        Args:
            cov_matrix: 协方差矩阵
            max_position: 单只股票最大权重

        Returns:
            最优权重 Series
        """
        stocks = cov_matrix.index
        n = len(stocks)
        Sigma = cov_matrix.values
        Sigma = self._ensure_positive_definite(Sigma)

        # 构建去相关矩阵: C = D^{-1/2} * Σ * D^{-1/2} (对协方差做波动率归一化，使目标函数等价于最小化平均相关系数)
        vols = np.sqrt(np.diag(Sigma))
        D_inv_half = np.diag(1.0 / vols)
        C = D_inv_half @ Sigma @ D_inv_half

        def objective(w):
            return w @ C @ w

        def gradient(w):
            return 2 * C @ w

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0, max_position) for _ in range(n)]

        w0 = np.ones(n) / n

        result = minimize(
            objective,
            w0,
            method="SLSQP",
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-10},
        )

        if not result.success:
            logger.warning(f"Max decorrelation optimization did not converge: {result.message}")
            weights = pd.Series(1.0 / n, index=stocks)
        else:
            weights = pd.Series(result.x, index=stocks)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== Black-Litterman模型 ====================

    def black_litterman_optimize(
        self,
        market_cap_weights: pd.Series,
        cov_matrix: pd.DataFrame,
        P: np.ndarray,
        Q: np.ndarray,
        Omega: np.ndarray,
        tau: float = 0.05,  # 均衡不确定性缩放: 越小越信任市场均衡，越大越信任主观观点
        risk_aversion: float = 1.0,
        delta: float = 2.5,  # 均衡风险厌恶系数，A股历史经验值2~4
        max_position: float = 0.10,
        long_only: bool = True,
    ) -> pd.Series:
        """
        Black-Litterman组合优化
        将模型观点(Q)与市场均衡结合，产生稳定的后验期望收益
        比直接使用因子模型期望收益更稳定，减少换手率30-50%

        Args:
            market_cap_weights: 市值加权权重(均衡权重)
            cov_matrix: 协方差矩阵
            P: 观点选择矩阵 (K x N), K个观点涉及N个资产
            Q: 观点收益向量 (K,), 每个观点的预期超额收益
            Omega: 观点不确定性矩阵 (K x K), 对角线为各观点方差
            tau: 不确定性缩放系数 (通常0.025-0.05)
            risk_aversion: 风险厌恶系数
            delta: 均衡风险厌恶系数 (用于计算隐含均衡收益)
            max_position: 单只股票最大权重
            long_only: 是否仅做多

        Returns:
            最优权重 Series
        """
        common = market_cap_weights.index.intersection(cov_matrix.index)
        n = len(common)
        if n < 2:
            return pd.Series(1.0 / n, index=common) if n > 0 else pd.Series()

        Sigma = cov_matrix.loc[common, common].values
        Sigma = self._ensure_positive_definite(Sigma)
        w_mkt = market_cap_weights.reindex(common).fillna(0).values

        # 隐含均衡收益: pi = delta * Sigma * w_mkt (从市值权重反推市场的一致预期收益)
        pi = delta * Sigma @ w_mkt

        # 后验期望收益: 贝叶斯融合均衡与观点，精度矩阵加权(越确定的观点权重越大)
        # mu_BL = inv(inv(tau*Sigma) + P'*inv(Omega)*P) * (inv(tau*Sigma)*pi + P'*inv(Omega)*Q)
        tau_Sigma = tau * Sigma
        try:
            inv_tau_Sigma = np.linalg.inv(tau_Sigma)
            inv_Omega = np.linalg.inv(Omega)
        except np.linalg.LinAlgError:
            logger.warning("BL: Matrix inversion failed, using equilibrium returns")  # 求逆失败则退回纯均衡收益
            mu_BL = pi
            return self.mean_variance_optimize(
                pd.Series(mu_BL, index=common),
                cov_matrix.loc[common, common],
                risk_aversion=risk_aversion,
                max_position=max_position,
                long_only=long_only,
            )

        # 后验精度矩阵和均值 (精度矩阵=逆协方差，数值上比直接求逆更稳定)
        posterior_precision = inv_tau_Sigma + P.T @ inv_Omega @ P
        posterior_mean_rhs = inv_tau_Sigma @ pi + P.T @ inv_Omega @ Q

        try:
            mu_BL = np.linalg.solve(posterior_precision, posterior_mean_rhs)
        except np.linalg.LinAlgError:
            mu_BL = pi

        # 用后验期望收益做均值方差优化
        return self.mean_variance_optimize(
            pd.Series(mu_BL, index=common),
            cov_matrix.loc[common, common],
            risk_aversion=risk_aversion,
            max_position=max_position,
            long_only=long_only,
        )

    # ==================== BL敏感性分析 ====================

    def black_litterman_sensitivity(
        self,
        market_cap_weights: pd.Series,
        cov_matrix: pd.DataFrame,
        P: np.ndarray,
        Q: np.ndarray,
        Omega: np.ndarray,
        tau_range: list[float] | None = None,
        risk_aversion: float = 1.0,
        delta: float = 2.5,
        max_position: float = 0.10,
        long_only: bool = True,
    ) -> dict[str, Any]:
        """
        Black-Litterman tau敏感性分析
        tau对BL结果影响极大，需扫描范围观察权重稳定性

        Args:
            tau_range: tau扫描范围, 默认[0.01, 0.025, 0.05, 0.075, 0.1]
        """
        if tau_range is None:
            tau_range = [0.01, 0.025, 0.05, 0.075, 0.1]

        results = {}
        for tau in tau_range:
            weights = self.black_litterman_optimize(
                market_cap_weights,
                cov_matrix,
                P,
                Q,
                Omega,
                tau=tau,
                risk_aversion=risk_aversion,
                delta=delta,
                max_position=max_position,
                long_only=long_only,
            )
            results[f"tau={tau:.3f}"] = {
                "weights": weights.to_dict(),
                "max_weight": weights.max(),
                "min_weight": weights[weights > 0].min() if (weights > 0).any() else 0,
                "n_positions": (weights > 1e-4).sum(),
            }

        # 计算权重稳定性: 各tau下权重的标准差
        all_weights = pd.DataFrame({k: pd.Series(v["weights"]) for k, v in results.items()})
        weight_stability = all_weights.std(axis=1).mean()

        return {
            "tau_results": results,
            "weight_stability": round(weight_stability, 6),
            "is_stable": weight_stability < 0.01,  # 各tau下权重标准差<1%视为稳定，否则需谨慎选择tau
        }

    # ==================== 稳健优化 ====================

    def robust_mean_variance_optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        return_uncertainty: pd.Series,
        risk_aversion: float = 1.0,
        kappa: float = 1.0,  # 不确定性惩罚: kappa=0退化为均值方差，kappa=1对应Box不确定性集
        max_position: float = 0.10,
        long_only: bool = True,
    ) -> pd.Series:
        """
        稳健优化 (收益不确定性)
        最差情况优化: max_w: w'mu_hat - kappa*|w|'*sigma_mu - lambda/2*w'Sigma*w
        对期望收益的估计误差进行惩罚，避免对噪声大的资产过度配置

        Args:
            expected_returns: 期望收益
            cov_matrix: 协方差矩阵
            return_uncertainty: 各资产期望收益的标准误
            risk_aversion: 风险厌恶系数
            kappa: 不确定性惩罚系数 (越大越保守)
            max_position: 单只股票最大权重
            long_only: 是否仅做多

        Returns:
            最优权重 Series
        """
        common = expected_returns.index.intersection(cov_matrix.index).intersection(return_uncertainty.index)
        n = len(common)
        if n < 2:
            return pd.Series(1.0 / n, index=common) if n > 0 else pd.Series()

        mu = expected_returns.reindex(common).values
        Sigma = cov_matrix.loc[common, common].values
        Sigma = self._ensure_positive_definite(Sigma)
        sigma_mu = return_uncertainty.reindex(common).values

        try:
            import cvxpy as cp
        except ImportError:
            # 回退: 缩减期望收益 (用mu-kappa*sigma_mu近似最差情况，牺牲鲁棒性但保证可解)
            adjusted_mu = mu - kappa * sigma_mu
            return self.mean_variance_optimize(
                pd.Series(adjusted_mu, index=common),
                cov_matrix.loc[common, common],
                risk_aversion=risk_aversion,
                max_position=max_position,
                long_only=long_only,
            )

        w = cp.Variable(n)

        # 目标: max w'mu - kappa*||diag(sigma_mu)*w||_1 - lambda/2 * w'Sigma*w
        # L1项惩罚不确定性大的资产权重，等价于最差情况下收益缩减
        objective = cp.Maximize(
            mu @ w - kappa * cp.norm1(cp.multiply(sigma_mu, w)) - risk_aversion / 2 * cp.quad_form(w, Sigma)
        )

        constraints = [cp.sum(w) == 1]
        if long_only:
            constraints.append(w >= 0)
        constraints.append(w <= max_position)

        problem = cp.Problem(objective, constraints)
        try:
            problem.solve(solver=cp.SCS, max_iters=2000)
        except cp.SolverError:
            problem.solve(solver=cp.ECOS, max_iters=500)

        if problem.status not in ["optimal", "optimal_inaccurate"] or w.value is None:
            # 回退到普通均值方差
            return self.mean_variance_optimize(
                expected_returns.reindex(common),
                cov_matrix.loc[common, common],
                risk_aversion=risk_aversion,
                max_position=max_position,
                long_only=long_only,
            )

        weights = np.maximum(w.value, 0)
        if weights.sum() > 0:
            weights = weights / weights.sum()
        return pd.Series(weights, index=common)

    # ==================== 交易成本感知优化 ====================

    def transaction_cost_aware_optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        prev_weights: pd.Series,
        risk_aversion: float = 1.0,
        linear_cost: float = 0.003,  # 单边30bps: 佣金~5bps+印花税10bps+滑点~15bps
        quadratic_cost: float = 0.0,  # 二次项模拟市场冲击(大单推高成交价)，小资金可设0
        max_position: float = 0.10,
        long_only: bool = True,
    ) -> pd.Series:
        """
        交易成本感知优化
        max w'mu - lambda/2*w'Sigma*w - lambda_tc_linear*|w-w_prev|_1 - lambda_tc_quad*||w-w_prev||^2

        Args:
            expected_returns: 期望收益
            cov_matrix: 协方差矩阵
            prev_weights: 上期权重
            risk_aversion: 风险厌恶系数
            linear_cost: 线性交易成本系数 (单边换手成本, 如0.003=30bps)
            quadratic_cost: 二次交易成本系数 (市场冲击)
            max_position: 单只股票最大权重
            long_only: 是否仅做多

        Returns:
            最优权重 Series
        """
        common = expected_returns.index.intersection(cov_matrix.index)
        n = len(common)
        if n < 2:
            return pd.Series(1.0 / n, index=common) if n > 0 else pd.Series()

        mu = expected_returns.reindex(common).values
        Sigma = cov_matrix.loc[common, common].values
        w_prev = prev_weights.reindex(common).fillna(0).values

        try:
            import cvxpy as cp
        except ImportError:
            # 回退: 在目标函数中加入二次惩罚 (无法建模L1，用L2近似线性成本)
            delta_w = expected_returns.reindex(common) - prev_weights.reindex(common)
            adjusted_returns = expected_returns.reindex(common) - quadratic_cost * delta_w
            return self.mean_variance_optimize(
                adjusted_returns,
                cov_matrix.loc[common, common],
                risk_aversion=risk_aversion,
                max_position=max_position,
                long_only=long_only,
            )

        w = cp.Variable(n)
        dw = w - w_prev  # 权重变化

        # 目标函数
        obj = mu @ w - risk_aversion / 2 * cp.quad_form(w, Sigma)

        # 线性交易成本: lambda_tc * |dw|_1 (L1范数产生稀疏换手，小调整直接归零)
        if linear_cost > 0:
            obj -= linear_cost * cp.norm1(dw)

        # 二次交易成本: lambda_tc_quad * ||dw||^2 (模拟价格冲击，大额交易推高成交价)
        if quadratic_cost > 0:
            obj -= quadratic_cost * cp.sum_squares(dw)

        objective = cp.Maximize(obj)
        constraints = [cp.sum(w) == 1]
        if long_only:
            constraints.append(w >= 0)
        constraints.append(w <= max_position)

        problem = cp.Problem(objective, constraints)
        try:
            problem.solve(solver=cp.SCS, max_iters=2000)
        except cp.SolverError:
            problem.solve(solver=cp.ECOS, max_iters=500)

        if problem.status not in ["optimal", "optimal_inaccurate"] or w.value is None:
            return self.mean_variance_optimize(
                expected_returns.reindex(common),
                cov_matrix.loc[common, common],
                risk_aversion=risk_aversion,
                max_position=max_position,
                long_only=long_only,
            )

        weights = np.maximum(w.value, 0)
        if weights.sum() > 0:
            weights = weights / weights.sum()
        return pd.Series(weights, index=common)

    # ==================== 优化结果分析 ====================

    def analyze_optimization(
        self, weights: pd.Series, expected_returns: pd.Series, cov_matrix: pd.DataFrame, risk_free_rate: float = 0.03
    ) -> dict:  # 3%无风险利率对应A股十年期国债均值
        """
        分析优化结果

        Args:
            weights: 优化后的权重
            expected_returns: 期望收益
            cov_matrix: 协方差矩阵
            risk_free_rate: 无风险利率

        Returns:
            优化结果分析
        """
        common = weights.index.intersection(expected_returns.index).intersection(cov_matrix.index)
        w = weights.reindex(common).fillna(0).values
        mu = expected_returns.reindex(common).values
        Sigma = cov_matrix.loc[common, common].values

        # 组合期望收益 (输入已经是年化收益)
        annual_return = w @ mu

        # 组合风险
        port_var = w @ Sigma @ w
        port_vol = np.sqrt(port_var)

        # 年化波动率 (输入协方差是日频，乘sqrt(252)年化)
        annual_vol = port_vol * np.sqrt(252)

        # 夏普比率
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0

        # 风险贡献
        mrc = Sigma @ w
        rc = w * mrc
        rc_pct = rc / port_var if port_var > 0 else rc

        # 有效持仓数: 1/Σw_i^2，等权时等于N，集中时趋近1
        effective_n = 1 / np.sum(w**2)

        return {
            "expected_return": annual_return,
            "volatility": annual_vol,
            "sharpe_ratio": sharpe,
            "effective_positions": effective_n,
            "max_weight": weights.max(),
            "min_weight": weights[weights > 0].min() if (weights > 0).any() else 0,
            "non_zero_positions": (weights > 1e-4).sum(),
            "risk_contributions": pd.Series(rc_pct, index=common),
        }

    # ==================== Mean-CVaR优化 (从RiskModel迁入) ====================

    @staticmethod
    def _ensure_positive_definite(matrix: np.ndarray) -> np.ndarray:
        """确保矩阵正定 (特征值截断: 相对最大特征值5%, 防止数值奇异导致优化失败)"""
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
            # 相对阈值: 截断到最大特征值的0.05%, 比绝对1e-10更合理
            # 绝对1e-10对金融数据(日频方差量级~1e-4)条件数可达1e6, 仍可能导致数值不稳定
            max_eig = eigenvalues.max()
            clip_threshold = max(max_eig * 1e-4, 1e-10)
            eigenvalues = np.maximum(eigenvalues, clip_threshold)
            return eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        except np.linalg.LinAlgError:
            return matrix

    def mean_cvar_optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        confidence: float = 0.95,
        risk_aversion: float = 1.0,
        max_weight: float = 0.05,  # CVaR优化更保守，5%上限防止尾部风险集中于少数资产
        min_weight: float = 0.0,
        long_only: bool = True,
    ) -> dict[str, Any]:
        """
        Mean-CVaR组合优化 (Rockafellar-Uryasev 2000)
        直接优化尾部风险而非方差，对非正态分布更稳健

        Args:
            expected_returns: 预期收益向量
            cov_matrix: 协方差矩阵
            confidence: CVaR置信水平
            risk_aversion: 风险厌恶系数
            max_weight: 单一资产最大权重
            min_weight: 单一资产最小权重
            long_only: 是否仅做多
        """
        try:
            import cvxpy as cp
        except ImportError:
            logger.warning("cvxpy not available, falling back to mean-variance")
            return self._mean_variance_fallback(expected_returns, cov_matrix, max_weight)

        N = len(expected_returns)
        w = cp.Variable(N)
        xi = cp.Variable()

        L = np.linalg.cholesky(self._ensure_positive_definite(cov_matrix))
        n_scenarios = 1000  # 1000个情景近似分布，平衡精度与求解速度
        Z = np.random.randn(n_scenarios, N)
        scenarios = Z @ L.T + expected_returns.reshape(1, -1)  # 蒙特卡洛生成收益情景

        losses = -scenarios @ w
        slack = cp.Variable(n_scenarios)

        # Rockafellar-Uryasev线性化: CVaR = ξ + E[max(loss-ξ,0)]/(1-α)，引入辅助变量slack
        cvar_term = xi + (1.0 / ((1 - confidence) * n_scenarios)) * cp.sum(slack)
        objective = cp.Minimize(-expected_returns @ w + risk_aversion * cvar_term)  # 最小化: 负收益 + λ*CVaR

        constraints = [
            cp.sum(w) == 1,
            slack >= 0,  # slack非负: 辅助约束，只计算超过ξ的损失
            slack >= losses - xi,  # slack >= loss - ξ: 捕获尾部损失超过VaR的部分
        ]

        if long_only:
            constraints.append(w >= min_weight)
        constraints.append(w <= max_weight)

        problem = cp.Problem(objective, constraints)
        try:
            problem.solve(solver=cp.ECOS, max_iters=500)
        except cp.SolverError:
            problem.solve(solver=cp.SCS, max_iters=2000)

        if problem.status not in ["optimal", "optimal_inaccurate"]:
            return self._mean_variance_fallback(expected_returns, cov_matrix, max_weight)

        weights = w.value
        if weights is None:
            return self._mean_variance_fallback(expected_returns, cov_matrix, max_weight)

        weights = np.maximum(weights, 0)
        weights = weights / weights.sum()

        return {
            "weights": weights,
            "expected_return": float(expected_returns @ weights),
            "cvar": float(
                xi.value
                + (1.0 / ((1 - confidence) * n_scenarios)) * np.sum(np.maximum(0, -scenarios @ weights - xi.value))
            ),
            "var": float(xi.value),
            "portfolio_vol": float(np.sqrt(weights @ cov_matrix @ weights)),
            "status": problem.status,
        }

    def _mean_variance_fallback(
        self, expected_returns: np.ndarray, cov_matrix: np.ndarray, max_weight: float
    ) -> dict[str, Any]:
        """均值-方差优化回退方案"""
        N = len(expected_returns)
        try:
            inv_cov = np.linalg.inv(cov_matrix)
            raw_weights = inv_cov @ expected_returns
            raw_weights = np.maximum(raw_weights, 0)
            if raw_weights.sum() > 0:
                weights = raw_weights / raw_weights.sum()
                weights = np.minimum(weights, max_weight)
                weights = weights / weights.sum()
            else:
                weights = np.ones(N) / N
        except np.linalg.LinAlgError:
            weights = np.ones(N) / N

        return {
            "weights": weights,
            "expected_return": float(expected_returns @ weights),
            "portfolio_vol": float(np.sqrt(weights @ cov_matrix @ weights)),
            "status": "fallback",
        }

    # ==================== HRP层次风险平价 (从ModelScorer迁入) ====================

    def hrp_optimize(self, cov_matrix: np.ndarray, index: pd.Index = None) -> pd.Series:
        """
        层次风险平价 (Hierarchical Risk Parity, Lopez de Prado 2016)
        基于相关性的聚类分配，避免矩阵求逆的不稳定性

        Args:
            cov_matrix: 协方差矩阵
            index: 资产索引
        """
        n = cov_matrix.shape[0]
        if index is None:
            index = pd.RangeIndex(n)

        if n < 3:
            return pd.Series(1.0 / n, index=index)

        try:
            # 从协方差矩阵正确推导相关矩阵
            # np.corrcoef(cov_matrix) 会将协方差矩阵行当作数据向量, 产生错误结果
            # 正确方法: corr_ij = cov_ij / (σ_i * σ_j)
            vols = np.sqrt(np.diag(cov_matrix))
            corr = cov_matrix / np.outer(vols, vols) if cov_matrix.ndim == 2 and cov_matrix.shape[0] > 1 else np.eye(n)
            # 距离矩阵: dist = sqrt(0.5*(1-corr))，将相关性映射为距离(完全相关→0，完全不相关→1)
            dist = np.sqrt(0.5 * (1 - corr))
            np.fill_diagonal(dist, 0)

            from scipy.cluster.hierarchy import linkage, to_tree

            condensed = dist[np.triu_indices(n, k=1)]
            link = linkage(condensed, method="single")  # single linkage避免链式效应弱于complete，但对金融数据更稳定

            # Lopez de Prado标准HRP: 按linkage树拓扑结构递归分配
            root = to_tree(link, rd=True)
            weights = self._hrp_recursive_split(root[0], cov_matrix)

            weights = weights / weights.sum()
            return pd.Series(weights, index=index)

        except Exception as e:
            logger.warning(f"HRP failed: {e}, falling back to equal weight")
            return pd.Series(1.0 / n, index=index)

    def _hrp_recursive_split(self, cluster_node, cov_matrix: np.ndarray) -> np.ndarray:
        """
        HRP递归二分分配 (Lopez de Prado 2016)
        按聚类树拓扑结构递归分配权重:
        1. 将当前节点分为左右子树
        2. 按逆方差比例分配权重给左右子树
        3. 递归到叶节点

        Args:
            cluster_node: scipy聚类树节点
            cov_matrix: 协方差矩阵

        Returns:
            权重向量 (n,)
        """

        # 叶节点: 返回1(后续归一化)
        if not cluster_node.left and not cluster_node.right:
            weights = np.zeros(cov_matrix.shape[0])
            weights[cluster_node.id] = 1.0
            return weights

        # 获取左右子树的叶子索引
        left_items = self._get_cluster_items(cluster_node.left)
        right_items = self._get_cluster_items(cluster_node.right)

        # 逆方差比例分配: 方差小的子树分配更多权重，与风险平价思想一致
        left_var = np.mean(np.diag(cov_matrix)[left_items]) if len(left_items) > 0 else 1e10
        right_var = np.mean(np.diag(cov_matrix)[right_items]) if len(right_items) > 0 else 1e10

        # alpha = 1 - left_var/(left_var+right_var): 左子树方差越小alpha越大(左分越多)
        alpha = 1.0 - left_var / (left_var + right_var) if (left_var + right_var) > 0 else 0.5

        # 递归
        left_weights = self._hrp_recursive_split(cluster_node.left, cov_matrix)
        right_weights = self._hrp_recursive_split(cluster_node.right, cov_matrix)

        return alpha * left_weights + (1 - alpha) * right_weights

    @staticmethod
    def _get_cluster_items(cluster_node) -> list[int]:
        """获取聚类节点下所有叶节点的索引列表"""
        if cluster_node is None:
            return []
        if cluster_node.left is None and cluster_node.right is None:
            return [cluster_node.id]
        items = []
        if cluster_node.left:
            items.extend(PortfolioOptimizer._get_cluster_items(cluster_node.left))
        if cluster_node.right:
            items.extend(PortfolioOptimizer._get_cluster_items(cluster_node.right))
        return items
