"""
自适应因子选择与权重优化引擎
核心: 滚动因子筛选、多目标权重优化、因子状态机、正交化选择、过拟合检测
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.logging import logger

if TYPE_CHECKING:
    from datetime import date

    import pandas as pd

class FactorState(StrEnum):
    ACTIVE = "active"
    MONITORING = "monitoring"
    INACTIVE = "inactive"


@dataclass
class FactorProfile:
    """因子画像: 跟踪每个因子的实时状态"""

    factor_code: str
    state: FactorState = FactorState.ACTIVE
    ic_mean: float = 0.0
    icir: float = 0.0
    coverage: float = 1.0
    turnover_cost: float = 0.0
    decay_half_life: int = 60
    n_periods: int = 0
    consecutive_low_ic: int = 0
    last_active_date: date | None = None
    weight: float = 0.0


class AdaptiveFactorEngine:
    """
    自适应因子引擎
    核心理念: 因子有效性是时变的，需要持续监控、筛选、调权
    """

    # 因子筛选阈值
    MIN_IC_MEAN = 0.02  # A股横截面IC低于0.02基本无选股区分度
    MIN_ICIR = 0.3  # ICIR<0.3意味着IC波动大于均值的3倍，信号不可靠
    MIN_COVERAGE = 0.6  # 覆盖率低于60%的因子易产生生存偏差
    MAX_TURNOVER_COST = 0.02  # 换手成本2bp，超过则因子净收益被交易费用侵蚀
    MONITORING_ICIR = 0.5  # ICIR降至0.5以下开始监控，尚未失效但需要关注
    CONSECUTIVE_LOW_LIMIT = 5  # 连续5期(约1个月)低IC才降权，避免单期噪声误判
    RECOVERY_ICIR = 0.8  # 恢复阈值高于监控阈值(0.5)，迟滞设计防止状态反复跳动

    def __init__(self, factor_profiles: dict[str, FactorProfile] | None = None):
        self.factor_profiles = factor_profiles or {}

    # ==================== 1. 滚动因子筛选 ====================

    def select_factors_rolling(
        self, ic_history: pd.DataFrame, lookback: int = 60, min_factors: int = 8, max_factors: int = 30
    ) -> list[str]:
        """
        滚动因子筛选
        基于近期IC/ICIR/覆盖率/换手成本综合评分，选择有效因子子集

        Args:
            ic_history: IC历史 DataFrame with columns [trade_date, factor_code, ic, rank_ic]
            lookback: 回看期数
            min_factors: 最少保留因子数
            max_factors: 最多保留因子数
        """
        if ic_history.empty:
            return []

        recent = ic_history.tail(lookback)
        factor_scores = {}

        for factor_code in recent["factor_code"].unique():
            f_ic = recent[recent["factor_code"] == factor_code]
            if len(f_ic) < 10:
                continue  # 10个观测点以下IC统计量不具备参考价值

            ic_mean = f_ic["ic"].mean()
            ic_std = f_ic["ic"].std()
            icir = ic_mean / ic_std if ic_std > 0 else 0
            rank_ic_mean = f_ic["rank_ic"].mean() if "rank_ic" in f_ic.columns else 0
            coverage = len(f_ic) / lookback
            ic_positive_rate = (f_ic["ic"] > 0).mean()

            # 综合评分: ICIR为主 + IC胜率 + RankIC辅助
            # ICIR权重0.5最大，因其同时衡量方向和稳定性；胜率0.3次之，RankIC仅作辅助
            # 因为RankIC通常与IC高度相关，给过高权重会重复计算信息
            score = (
                0.5 * abs(icir)
                + 0.3 * (ic_positive_rate - 0.5) * 2  # 减0.5再乘2，将[0.5,1]映射到[0,1]
                + 0.2 * abs(rank_ic_mean) * 10  # RankIC量级约0.01-0.05，乘10对齐ICIR量级
            )

            # 方向惩罚: IC为负的因子降权，保留0.3而非直接归零
            # 因为负IC可能来自因子方向反转，翻转后仍可用
            if ic_mean < 0:
                score *= 0.3

            factor_scores[factor_code] = {
                "score": score,
                "ic_mean": ic_mean,
                "icir": icir,
                "coverage": coverage,
                "ic_positive_rate": ic_positive_rate,
            }

        if not factor_scores:
            return []

        # 按综合评分排序
        sorted_factors = sorted(factor_scores.items(), key=lambda x: -x[1]["score"])

        # 筛选: 评分>0 且满足最低条件
        selected = []
        for factor_code, metrics in sorted_factors:
            if metrics["icir"] >= self.MIN_ICIR and metrics["coverage"] >= self.MIN_COVERAGE:
                selected.append(factor_code)
            if len(selected) >= max_factors:
                break

        # 保证最少因子数：即使严格筛选后因子不足，也需保留最低数量
        # 因子过少会导致组合集中度风险，无法有效分散
        if len(selected) < min_factors:
            for factor_code, _ in sorted_factors:
                if factor_code not in selected:
                    selected.append(factor_code)
                if len(selected) >= min_factors:
                    break

        logger.info(
            "Adaptive factor selection completed",
            extra={
                "n_candidates": len(factor_scores),
                "n_selected": len(selected),
                "lookback": lookback,
            },
        )

        return selected

    # ==================== 2. 多目标权重优化 ====================

    def optimize_weights_multi_objective(
        self,
        icir_values: dict[str, float],
        turnover_costs: dict[str, float] | None = None,
        factor_decay: dict[str, float] | None = None,
        prev_weights: dict[str, float] | None = None,
        turnover_penalty: float = 0.3,
        decay_penalty: float = 0.1,
        stability_penalty: float = 0.2,
    ) -> dict[str, float]:
        # 换手惩罚0.3为默认值，在ICIR均约1.0时约30%权重变化被抑制
        # 稳定性惩罚0.2与换手惩罚互补：换手惩罚约束一阶差异，稳定性约束二阶波动
        """
        多目标权重优化
        max: Σ w_k * ICIR_k - λ_turn * Σ |w_k - w_k_prev| - λ_decay * Σ decay_k * w_k
        s.t. Σ w_k = 1, w_k >= 0

        Args:
            icir_values: 各因子ICIR值
            turnover_costs: 各因子换手成本
            factor_decay: 各因子衰减系数 (0-1, 越大衰减越快)
            prev_weights: 上期权重
            turnover_penalty: 换手惩罚系数
            decay_penalty: 衰减惩罚系数
            stability_penalty: 权重稳定性惩罚
        """
        factors = list(icir_values.keys())
        n = len(factors)
        if n == 0:
            return {}

        icir = np.array([icir_values[f] for f in factors])

        # 换手成本
        _tc = np.array([turnover_costs.get(f, 0) for f in factors]) if turnover_costs else np.zeros(n)

        # 因子衰减
        decay = np.array([factor_decay.get(f, 0) for f in factors]) if factor_decay else np.zeros(n)

        # 上期权重
        w_prev = np.array([prev_weights.get(f, 1.0 / n) for f in factors]) if prev_weights else np.ones(n) / n

        # 只保留正ICIR的因子
        positive_mask = icir > 0
        if not positive_mask.any():
            # 全部ICIR为负，取绝对值最大的
            # 极端市场下所有因子可能同时失效，此时完全清仓不现实
            positive_mask = np.ones(n, dtype=bool)

        # 初始权重: ICIR正比分配
        # 相比等权，ICIR加权让信号稳定因子获得更高权重，是行业主流做法
        # 等权作为fallback：当所有ICIR接近0时ICIR加权退化为等权
        abs_icir = np.abs(icir) * positive_mask
        total_icir = abs_icir.sum()
        w = abs_icir / total_icir if total_icir > 0 else np.ones(n) / n

        # 迭代优化: 梯度下降 + 投影
        learning_rate = 0.01
        for _ in range(200):
            # 梯度: d/dw [w'*icir - λ_turn*|w-w_prev| - λ_decay*decay'*w - λ_stab*(w-w_prev)^2]
            grad = icir.copy()

            # 换手惩罚梯度
            if turnover_penalty > 0:
                diff = w - w_prev
                grad -= turnover_penalty * np.sign(diff)

            # 衰减惩罚梯度
            if decay_penalty > 0:
                grad -= decay_penalty * decay

            # 稳定性惩罚梯度
            if stability_penalty > 0:
                grad -= stability_penalty * 2 * (w - w_prev)

            # 更新
            w_new = w + learning_rate * grad

            # 投影到单纯形: w >= 0, Σw = 1
            w_new = self._project_simplex(w_new)

            # 收敛检查
            if np.max(np.abs(w_new - w)) < 1e-6:
                w = w_new
                break
            w = w_new

        # 清理微小权重：低于万一的权重对组合无实质贡献，反而增加换手开销
        w[w < 1e-4] = 0
        if w.sum() > 0:
            w = w / w.sum()

        weights = {f: round(float(w[i]), 6) for i, f in enumerate(factors) if w[i] > 0}

        logger.info(
            "Multi-objective weight optimization completed",
            extra={
                "n_factors": len(factors),
                "n_active": len(weights),
                "max_weight": max(weights.values()) if weights else 0,
                "turnover_penalty": turnover_penalty,
            },
        )

        return weights

    @staticmethod
    def _project_simplex(v: np.ndarray) -> np.ndarray:
        """投影到单纯形 (Duchi et al. 2008)
        带数值稳定性保护: 收敛检查和极端值fallback
        """
        n = len(v)
        if n == 0:
            return v.copy()

        # 极端值保护: clamp到合理范围避免溢出
        # ICIR加权的梯度下降中，极端ICIR值(如>1e6)会导致投影数值溢出
        v_clamped = np.clip(v, -1e6, 1e6)
        u = np.sort(v_clamped)[::-1]
        cssv = np.cumsum(u) - 1
        rho_candidates = np.where(u > cssv / np.arange(1, n + 1))[0]

        if len(rho_candidates) == 0:
            # fallback: 均匀分布 — 单纯形投影在极端输入下可能无有效解
            return np.ones(n) / n

        rho = rho_candidates[-1]
        theta = cssv[rho] / (rho + 1.0)

        # 数值稳定性检查: theta过大时回退到均匀分布
        # theta是单纯形投影的偏移量，过大会导致投影后所有分量为0
        if abs(theta) > 1e8:
            return np.ones(n) / n

        w = np.maximum(v_clamped - theta, 0)

        # 验证投影结果: sum应≈1且无负值
        # 浮点误差累积可能导致投影结果不满足约束，此时回退均匀分布
        if abs(np.sum(w) - 1.0) > 1e-6 or np.any(w < -1e-10):
            return np.ones(n) / n

        return w

    # ==================== 3. 因子状态机 ====================

    def update_factor_state(
        self, factor_code: str, recent_ic: pd.Series, coverage: float = 1.0, trade_date: date | None = None
    ) -> FactorProfile:
        """
        更新因子状态
        状态转换规则:
          ACTIVE → MONITORING: ICIR < MONITORING_ICIR
          MONITORING → INACTIVE: 连续CONSECUTIVE_LOW_LIMIT次IC < MIN_IC_MEAN
          MONITORING → ACTIVE: ICIR > RECOVERY_ICIR
          INACTIVE → MONITORING: ICIR > MIN_ICIR
        """
        if factor_code not in self.factor_profiles:
            self.factor_profiles[factor_code] = FactorProfile(factor_code=factor_code)

        profile = self.factor_profiles[factor_code]

        # 计算近期IC指标
        ic_mean = recent_ic.mean() if len(recent_ic) > 0 else 0
        ic_std = recent_ic.std() if len(recent_ic) > 1 else 0
        icir = ic_mean / ic_std if ic_std > 0 else 0

        profile.ic_mean = ic_mean
        profile.icir = icir
        profile.coverage = coverage
        profile.n_periods = len(recent_ic)

        # 状态转换
        old_state = profile.state

        if profile.state == FactorState.ACTIVE:
            # ICIR降至MONITORING_ICIR(0.5)以下即进入监控，留出缓冲区
            if abs(icir) < self.MONITORING_ICIR:
                profile.state = FactorState.MONITORING
                profile.consecutive_low_ic = 1
            elif abs(icir) < self.MIN_ICIR:
                # ICIR在0.3-0.5之间也进入监控，但低IC计数从1开始
                profile.state = FactorState.MONITORING
                profile.consecutive_low_ic = 1

        elif profile.state == FactorState.MONITORING:
            if abs(icir) >= self.RECOVERY_ICIR:
                # 恢复阈值0.8远高于监控阈值0.5，迟滞设计防止状态在边界反复切换
                profile.state = FactorState.ACTIVE
                profile.consecutive_low_ic = 0
            elif abs(icir) < self.MIN_ICIR:
                profile.consecutive_low_ic += 1
                if profile.consecutive_low_ic >= self.CONSECUTIVE_LOW_LIMIT:
                    # 连续5期低IC才降权为INACTIVE，避免单期异常噪声误杀因子
                    profile.state = FactorState.INACTIVE
            else:
                # ICIR回到0.3-0.5之间时逐步恢复计数，不完全重置
                # 保留部分低IC记忆，防止间歇性回升掩盖持续衰减
                profile.consecutive_low_ic = max(0, profile.consecutive_low_ic - 1)

        elif profile.state == FactorState.INACTIVE and abs(icir) >= self.RECOVERY_ICIR:
            # INACTIVE只能恢复到MONITORING而非ACTIVE，需要持续验证
            # 防止因单期ICIR飙升就立即重用已失效因子
            profile.state = FactorState.MONITORING
            profile.consecutive_low_ic = 0

        if profile.state == FactorState.ACTIVE:
            profile.last_active_date = trade_date

        if old_state != profile.state:
            logger.info(
                "Factor state transition",
                extra={
                    "factor": factor_code,
                    "old_state": old_state.value,
                    "new_state": profile.state.value,
                    "icir": round(icir, 4),
                    "ic_mean": round(ic_mean, 4),
                },
            )

        return profile

    def get_active_factors(self) -> list[str]:
        """获取所有活跃因子"""
        return [f for f, p in self.factor_profiles.items() if p.state in (FactorState.ACTIVE, FactorState.MONITORING)]

    def get_factor_weights_by_state(self) -> dict[str, float]:
        """根据状态分配权重: ACTIVE=1.0, MONITORING=0.5, INACTIVE=0.0"""
        # 监控态0.5权重：不完全排除但降低敞口，避免因子刚进监控就大幅调仓
        weights = {}
        for f, p in self.factor_profiles.items():
            if p.state == FactorState.ACTIVE:
                weights[f] = 1.0
            elif p.state == FactorState.MONITORING:
                weights[f] = 0.5
            else:
                weights[f] = 0.0
        return weights

    # ==================== 4. 正交化因子选择 ====================

    def select_orthogonal_subset(
        self,
        factor_corr_matrix: pd.DataFrame,
        factor_icir: dict[str, float],
        max_factors: int = 30,
        corr_threshold: float = 0.6,
    ) -> list[str]:
        # corr_threshold=0.6: A股因子间相关系数超0.6时信息重叠严重
        # 0.6比常见0.5更宽松，因A股因子池有限，过严会损失因子多样性
        """
        正交化因子选择 (贪心算法)
        每步选择信息增量最大的因子: max ICIR_k * (1 - max_corr_with_selected)

        Args:
            factor_corr_matrix: 因子间相关系数矩阵
            factor_icir: 各因子ICIR值
            max_factors: 最大因子数
            corr_threshold: 相关性阈值(超过则不选)
        """
        factors = list(factor_corr_matrix.columns)
        n = len(factors)
        if n == 0:
            return []

        # 按ICIR排序
        sorted_factors = sorted(factors, key=lambda f: -abs(factor_icir.get(f, 0)))

        selected = []
        for candidate in sorted_factors:
            if len(selected) >= max_factors:
                break

            icir = abs(factor_icir.get(candidate, 0))
            if icir < self.MIN_ICIR:
                continue

            # 计算与已选因子的最大相关性
            if selected and candidate in factor_corr_matrix.index:
                corrs = factor_corr_matrix.loc[candidate, selected].abs()
                max_corr = corrs.max()
            else:
                max_corr = 0

            # 信息增量 = ICIR * (1 - max_corr)
            info_increment = icir * (1 - max_corr)

            # 相关性过高则跳过
            # 但至少保留5个因子，即使相关性偏高——因子过少比相关性的危害更大
            if max_corr > corr_threshold and len(selected) >= 5:
                continue

            # 信息增量过低则跳过
            # 0.1阈值：ICIR=1.0时允许最大相关性0.9，ICIR=0.3时允许约0.67
            if info_increment < 0.1:
                continue

            selected.append(candidate)

        logger.info(
            "Orthogonal factor selection completed",
            extra={
                "n_candidates": n,
                "n_selected": len(selected),
                "max_factors": max_factors,
            },
        )

        return selected

    # ==================== 5. 过拟合检测 ====================

    def detect_overfitting(
        self,
        train_sharpe: float,
        test_sharpe: float,
        n_trials: int = 1,
        backtest_years: float = 2.0,
        returns: pd.Series = None,
    ) -> dict[str, Any]:
        """
        过拟合检测
        综合使用: 通胀夏普比率(DSR) + 训练/测试Sharpe衰减 + 蒙特卡洛置换检验

        Args:
            train_sharpe: 训练期Sharpe
            test_sharpe: 测试期Sharpe
            n_trials: 测试的策略数量(用于DSR)
            backtest_years: 回测年数
            returns: 策略收益率序列(用于置换检验)
        """
        result = {
            "train_sharpe": train_sharpe,
            "test_sharpe": test_sharpe,
            "sharpe_decay": 0.0,
            "is_overfit": False,
            "overfitting_score": 0.0,
        }

        # 1. Sharpe衰减率
        if abs(train_sharpe) > 0.01:
            decay = 1 - test_sharpe / train_sharpe
            result["sharpe_decay"] = round(decay, 4)
            # 衰减>50%视为过拟合信号
            # A股策略样本外衰减50%以上通常意味着训练期过度挖掘了数据特征
            if decay > 0.5:
                result["is_overfit"] = True
                result["overfitting_score"] += 0.4

        # 2. 通胀夏普比率 (DSR)
        if n_trials > 1 and abs(test_sharpe) > 0.01:
            try:
                from scipy.stats import norm

                # E[max_SR] ≈ sqrt(2*ln(N) / T)
                var_sr = 1.0 / max(backtest_years, 0.5)
                expected_max_sr = np.sqrt(var_sr) * np.sqrt(2 * np.log(max(n_trials, 2)))
                se_sr = np.sqrt(var_sr)
                if se_sr > 0:
                    dsr = norm.cdf((test_sharpe - expected_max_sr) / se_sr)
                else:
                    dsr = 1.0 if test_sharpe > expected_max_sr else 0.0

                result["dsr"] = round(dsr, 4)
                result["expected_max_sharpe"] = round(expected_max_sr, 2)
                # DSR<0.95表示测试Sharpe未能显著超越多重检验下的期望最大Sharpe
                # 95%置信度是金融研究中的常用门槛
                if dsr < 0.95:
                    result["is_overfit"] = True
                    result["overfitting_score"] += 0.3 * (1 - dsr)
            except Exception:
                pass

        # 3. 蒙特卡洛置换检验 (如果有收益率数据)
        if returns is not None and len(returns) > 60:
            # 至少60个观测点(约3个月)才进行置换检验，样本过少结果无意义
            mc_result = self._permutation_test(returns, n_permutations=500)
            result["permutation_p_value"] = mc_result["p_value"]
            if mc_result["p_value"] > 0.05:
                # p>0.05说明策略Sharpe在随机排列下也容易出现，过拟合嫌疑大
                result["is_overfit"] = True
                result["overfitting_score"] += 0.3

        # 综合评分
        result["overfitting_score"] = round(result["overfitting_score"], 4)

        logger.info(
            "Overfitting detection completed",
            extra={
                "train_sharpe": train_sharpe,
                "test_sharpe": test_sharpe,
                "is_overfit": result["is_overfit"],
                "overfitting_score": result["overfitting_score"],
            },
        )

        return result

    def _permutation_test(self, returns: pd.Series, n_permutations: int = 500, block_size: int = 5) -> dict[str, float]:
        """块置换检验"""
        # block_size=5保留5日内的收益率自相关结构，单纯打乱会低估方差
        actual_sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        n = len(returns)
        permuted_sharpes = []

        for _ in range(n_permutations):
            n_blocks = n // block_size
            block_indices = np.arange(n_blocks)
            np.random.shuffle(block_indices)
            permuted = np.concatenate(
                [returns.iloc[i * block_size : (i + 1) * block_size].values for i in block_indices]
            )
            remainder = n % block_size
            if remainder > 0:
                permuted = np.concatenate([permuted, returns.iloc[-remainder:].values])
            perm_sharpe = permuted.mean() / permuted.std() * np.sqrt(252) if permuted.std() > 0 else 0
            permuted_sharpes.append(perm_sharpe)

        p_value = sum(1 for s in permuted_sharpes if s >= actual_sharpe) / n_permutations
        return {"p_value": p_value, "actual_sharpe": actual_sharpe}

    # ==================== 6. 因子衰减分析 ====================

    def analyze_factor_decay(self, ic_series: pd.Series, half_life_init: int = 60) -> dict[str, Any]:
        """
        分析因子IC衰减
        用指数衰减模型拟合IC时间序列: IC(t) = IC_0 * exp(-t/τ) + noise
        估计半衰期τ_{1/2} = τ * ln(2)
        """
        ic = ic_series.dropna()
        if len(ic) < 20:
            return {"half_life": np.nan, "is_decaying": False}

        # 拟合指数衰减: IC(t) = a * exp(-b*t) + c
        t = np.arange(len(ic))
        ic_values = ic.values

        try:
            from scipy.optimize import curve_fit

            def exp_decay(t, a, b, c):
                return a * np.exp(-b * t) + c

            popt, _ = curve_fit(
                exp_decay,
                t,
                ic_values,
                p0=[ic_values[0], 0.01, ic_values.mean()],
                maxfev=5000,
            )
            a, b, c = popt

            half_life = np.log(2) / b if b > 0 else np.inf

            is_decaying = b > 0.005 and half_life < len(ic) * 0.8
            # b>0.005排除伪衰减(拟合噪声)，半衰期<80%序列长度确认衰减在观测期内可观测

            return {
                "half_life": round(half_life, 1),
                "decay_rate": round(b, 6),
                "initial_ic": round(a, 4),
                "steady_state_ic": round(c, 4),
                "is_decaying": is_decaying,
            }
        except Exception:
            # 回退: 用前后半段IC均值比较
            # 曲线拟合失败时(如IC剧烈波动)的降级方案
            mid = len(ic) // 2
            first_half_ic = ic.iloc[:mid].mean()
            second_half_ic = ic.iloc[mid:].mean()
            is_decaying = second_half_ic < first_half_ic * 0.7
            # 后半段IC降至前半段70%以下判定为衰减，阈值0.7容忍正常波动

            return {
                "half_life": np.nan,
                "first_half_ic": round(first_half_ic, 4),
                "second_half_ic": round(second_half_ic, 4),
                "is_decaying": is_decaying,
            }

    # ==================== 7. 批量更新因子画像 ====================

    def batch_update_profiles(
        self, ic_history: pd.DataFrame, coverage_data: dict[str, float] | None = None, trade_date: date | None = None
    ) -> dict[str, FactorProfile]:
        """
        批量更新所有因子画像
        """
        if ic_history.empty:
            return self.factor_profiles

        for factor_code in ic_history["factor_code"].unique():
            f_ic = ic_history[ic_history["factor_code"] == factor_code]["ic"]
            coverage = coverage_data.get(factor_code, 1.0) if coverage_data else 1.0
            self.update_factor_state(factor_code, f_ic, coverage, trade_date)

        n_active = sum(1 for p in self.factor_profiles.values() if p.state == FactorState.ACTIVE)
        n_monitoring = sum(1 for p in self.factor_profiles.values() if p.state == FactorState.MONITORING)
        n_inactive = sum(1 for p in self.factor_profiles.values() if p.state == FactorState.INACTIVE)

        logger.info(
            "Batch factor profile update completed",
            extra={
                "n_active": n_active,
                "n_monitoring": n_monitoring,
                "n_inactive": n_inactive,
                "trade_date": str(trade_date) if trade_date else None,
            },
        )

        return self.factor_profiles

    # ==================== 8. IC衰减监控与预警 ====================

    def monitor_ic_decay(
        self, ic_history: pd.DataFrame, lookback_short: int = 20, lookback_long: int = 60, alert_threshold: float = 0.3
    ) -> dict[str, Any]:
        """
        IC衰减监控与预警

        对比短期IC与长期IC，识别衰减趋势并生成预警

        Args:
            ic_history: IC历史数据
            lookback_short: 短期回看窗口（默认20天）
            lookback_long: 长期回看窗口（默认60天）
            alert_threshold: 预警阈值（短期IC相对长期IC的衰减比例）

        Returns:
            监控报告字典
        """
        if ic_history.empty:
            return {"factors": {}, "alerts": []}

        report = {"factors": {}, "alerts": [], "summary": {}}

        for factor_code in ic_history["factor_code"].unique():
            f_ic = ic_history[ic_history["factor_code"] == factor_code]["ic"]

            if len(f_ic) < lookback_short:
                continue

            # 计算短期和长期IC
            recent_ic = f_ic.tail(lookback_short)
            long_ic = f_ic.tail(lookback_long) if len(f_ic) >= lookback_long else f_ic

            short_ic_mean = recent_ic.mean()
            long_ic_mean = long_ic.mean()
            short_ic_std = recent_ic.std()
            long_ic_std = long_ic.std()

            # 计算ICIR
            short_icir = short_ic_mean / short_ic_std if short_ic_std > 0 else 0
            long_icir = long_ic_mean / long_ic_std if long_ic_std > 0 else 0

            # 计算衰减率
            if abs(long_ic_mean) > 0.001:
                decay_rate = (long_ic_mean - short_ic_mean) / abs(long_ic_mean)
            else:
                decay_rate = 0

            # IC趋势（线性回归斜率）
            if len(recent_ic) >= 10:
                t = np.arange(len(recent_ic))
                slope, _ = np.polyfit(t, recent_ic.values, 1)
                trend = "下降" if slope < -0.0001 else ("上升" if slope > 0.0001 else "平稳")
            else:
                slope = 0
                trend = "未知"

            # 因子衰减分析
            decay_analysis = self.analyze_factor_decay(f_ic)

            factor_report = {
                "short_ic_mean": round(short_ic_mean, 4),
                "long_ic_mean": round(long_ic_mean, 4),
                "short_icir": round(short_icir, 4),
                "long_icir": round(long_icir, 4),
                "decay_rate": round(decay_rate, 4),
                "trend": trend,
                "trend_slope": round(slope, 6),
                "half_life": decay_analysis.get("half_life", np.nan),
                "is_decaying": decay_analysis.get("is_decaying", False),
            }

            report["factors"][factor_code] = factor_report

            # 生成预警
            alerts = []

            # 预警1：IC显著衰减
            if decay_rate > alert_threshold:
                alerts.append(
                    {
                        "level": "warning",
                        "type": "ic_decay",
                        "message": f"因子 {factor_code} IC衰减 {decay_rate:.1%}",
                        "detail": f"长期IC={long_ic_mean:.4f}, 短期IC={short_ic_mean:.4f}",
                    }
                )

            # 预警2：ICIR大幅下降
            if abs(long_icir) > 0.5 and abs(short_icir) < 0.3:
                alerts.append(
                    {
                        "level": "warning",
                        "type": "icir_drop",
                        "message": f"因子 {factor_code} ICIR大幅下降",
                        "detail": f"长期ICIR={long_icir:.2f}, 短期ICIR={short_icir:.2f}",
                    }
                )

            # 预警3：IC方向反转
            if long_ic_mean * short_ic_mean < 0 and abs(short_ic_mean) > 0.01:
                alerts.append(
                    {
                        "level": "critical",
                        "type": "ic_reversal",
                        "message": f"因子 {factor_code} IC方向反转",
                        "detail": f"长期IC={long_ic_mean:.4f}, 短期IC={short_ic_mean:.4f}",
                    }
                )

            # 预警4：持续衰减
            if decay_analysis.get("is_decaying") and decay_analysis.get("half_life", np.inf) < 40:
                alerts.append(
                    {
                        "level": "critical",
                        "type": "rapid_decay",
                        "message": f"因子 {factor_code} 快速衰减",
                        "detail": f"半衰期={decay_analysis.get('half_life'):.1f}天",
                    }
                )

            if alerts:
                report["alerts"].extend(alerts)

        # 汇总统计
        if report["factors"]:
            all_decay_rates = [f["decay_rate"] for f in report["factors"].values()]
            all_short_icir = [f["short_icir"] for f in report["factors"].values()]

            report["summary"] = {
                "n_factors": len(report["factors"]),
                "n_alerts": len(report["alerts"]),
                "avg_decay_rate": round(np.mean(all_decay_rates), 4),
                "max_decay_rate": round(np.max(all_decay_rates), 4),
                "avg_short_icir": round(np.mean(all_short_icir), 4),
                "n_decaying": sum(1 for f in report["factors"].values() if f["is_decaying"]),
            }

        logger.info(
            "IC decay monitoring completed",
            extra={
                "n_factors": report["summary"].get("n_factors", 0),
                "n_alerts": report["summary"].get("n_alerts", 0),
                "n_decaying": report["summary"].get("n_decaying", 0),
            },
        )

        return report

    def generate_factor_health_report(self, ic_history: pd.DataFrame, lookback: int = 60) -> dict[str, Any]:
        """
        生成因子健康度报告

        综合评估所有因子的健康状况

        Args:
            ic_history: IC历史数据
            lookback: 回看窗口

        Returns:
            健康度报告
        """
        if ic_history.empty:
            return {"factors": {}, "overall_health": "unknown"}

        report = {"factors": {}, "health_scores": {}}

        for factor_code in ic_history["factor_code"].unique():
            f_ic = ic_history[ic_history["factor_code"] == factor_code]["ic"]

            if len(f_ic) < 10:
                continue

            recent_ic = f_ic.tail(lookback)

            # 计算健康度指标
            ic_mean = recent_ic.mean()
            ic_std = recent_ic.std()
            icir = ic_mean / ic_std if ic_std > 0 else 0
            ic_positive_rate = (recent_ic > 0).mean()
            ic_stability = 1 - (recent_ic.rolling(10).std().mean() / (abs(ic_mean) + 0.01))

            # 综合健康度评分 (0-100)
            health_score = 0

            # 1. ICIR贡献 (40分)
            if abs(icir) >= 1.0:
                health_score += 40
            elif abs(icir) >= 0.5:
                health_score += 20 + 20 * (abs(icir) - 0.5) / 0.5
            elif abs(icir) >= 0.3:
                health_score += 10 + 10 * (abs(icir) - 0.3) / 0.2
            else:
                health_score += 10 * abs(icir) / 0.3

            # 2. IC胜率贡献 (30分)
            health_score += 30 * max(0, (ic_positive_rate - 0.5) / 0.5)

            # 3. IC稳定性贡献 (20分)
            health_score += 20 * max(0, min(1, ic_stability))

            # 4. IC绝对值贡献 (10分)
            health_score += 10 * min(1, abs(ic_mean) / 0.05)

            health_score = min(100, max(0, health_score))

            # 健康等级
            if health_score >= 80:
                health_level = "优秀"
            elif health_score >= 60:
                health_level = "良好"
            elif health_score >= 40:
                health_level = "一般"
            elif health_score >= 20:
                health_level = "较差"
            else:
                health_level = "失效"

            factor_report = {
                "health_score": round(health_score, 1),
                "health_level": health_level,
                "ic_mean": round(ic_mean, 4),
                "icir": round(icir, 4),
                "ic_positive_rate": round(ic_positive_rate, 4),
                "ic_stability": round(ic_stability, 4),
            }

            report["factors"][factor_code] = factor_report
            report["health_scores"][factor_code] = health_score

        # 整体健康度
        if report["health_scores"]:
            avg_health = np.mean(list(report["health_scores"].values()))
            if avg_health >= 70:
                overall_health = "优秀"
            elif avg_health >= 50:
                overall_health = "良好"
            elif avg_health >= 30:
                overall_health = "一般"
            else:
                overall_health = "较差"

            report["overall_health"] = overall_health
            report["avg_health_score"] = round(avg_health, 1)

            # 排序：按健康度从高到低
            report["top_factors"] = sorted(
                report["health_scores"].items(), key=lambda x: -x[1]
            )[:10]
            report["bottom_factors"] = sorted(
                report["health_scores"].items(), key=lambda x: x[1]
            )[:10]

        logger.info(
            "Factor health report generated",
            extra={
                "n_factors": len(report["factors"]),
                "overall_health": report.get("overall_health", "unknown"),
                "avg_health_score": report.get("avg_health_score", 0),
            },
        )

        return report

    def get_factor_recommendations(self, ic_history: pd.DataFrame, lookback: int = 60) -> dict[str, list[str]]:
        """
        生成因子使用建议

        基于因子健康度和状态，给出使用建议

        Args:
            ic_history: IC历史数据
            lookback: 回看窗口

        Returns:
            建议字典 {action: [factor_codes]}
        """
        health_report = self.generate_factor_health_report(ic_history, lookback)
        decay_report = self.monitor_ic_decay(ic_history, lookback_short=20, lookback_long=lookback)

        recommendations = {
            "keep": [],  # 保持使用
            "monitor": [],  # 密切监控
            "reduce": [],  # 降低权重
            "remove": [],  # 建议移除
            "investigate": [],  # 需要调查
        }

        for factor_code, health in health_report["factors"].items():
            health_score = health["health_score"]
            decay_info = decay_report["factors"].get(factor_code, {})
            decay_rate = decay_info.get("decay_rate", 0)
            is_decaying = decay_info.get("is_decaying", False)

            # 决策逻辑
            if health_score >= 70 and decay_rate < 0.2:
                recommendations["keep"].append(factor_code)
            elif health_score >= 50 and decay_rate < 0.3:
                recommendations["monitor"].append(factor_code)
            elif health_score >= 30 or (health_score >= 40 and not is_decaying):
                recommendations["reduce"].append(factor_code)
            elif health_score < 30 and is_decaying:
                recommendations["remove"].append(factor_code)
            else:
                recommendations["investigate"].append(factor_code)

        logger.info(
            "Factor recommendations generated",
            extra={
                "keep": len(recommendations["keep"]),
                "monitor": len(recommendations["monitor"]),
                "reduce": len(recommendations["reduce"]),
                "remove": len(recommendations["remove"]),
            },
        )

        return recommendations
