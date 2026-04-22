"""
自适应因子选择与权重优化引擎
核心: 滚动因子筛选、多目标权重优化、因子状态机、正交化选择、过拟合检测
"""
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import date, datetime
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from app.core.logging import logger


class FactorState(str, Enum):
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
    last_active_date: Optional[date] = None
    weight: float = 0.0


class AdaptiveFactorEngine:
    """
    自适应因子引擎
    核心理念: 因子有效性是时变的，需要持续监控、筛选、调权
    """

    # 因子筛选阈值
    MIN_IC_MEAN = 0.02          # 最低IC均值
    MIN_ICIR = 0.3              # 最低ICIR
    MIN_COVERAGE = 0.6          # 最低覆盖率
    MAX_TURNOVER_COST = 0.02    # 最大换手成本
    MONITORING_ICIR = 0.5       # 低于此值进入监控
    CONSECUTIVE_LOW_LIMIT = 5   # 连续低IC次数触发降权
    RECOVERY_ICIR = 0.8         # 恢复阈值

    def __init__(self, factor_profiles: Optional[Dict[str, FactorProfile]] = None):
        self.factor_profiles = factor_profiles or {}

    # ==================== 1. 滚动因子筛选 ====================

    def select_factors_rolling(self, ic_history: pd.DataFrame,
                                lookback: int = 60,
                                min_factors: int = 8,
                                max_factors: int = 30) -> List[str]:
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

        for factor_code in recent['factor_code'].unique():
            f_ic = recent[recent['factor_code'] == factor_code]
            if len(f_ic) < 10:
                continue

            ic_mean = f_ic['ic'].mean()
            ic_std = f_ic['ic'].std()
            icir = ic_mean / ic_std if ic_std > 0 else 0
            rank_ic_mean = f_ic['rank_ic'].mean() if 'rank_ic' in f_ic.columns else 0
            coverage = len(f_ic) / lookback
            ic_positive_rate = (f_ic['ic'] > 0).mean()

            # 综合评分: ICIR为主 + IC胜率 + RankIC辅助
            score = (
                0.5 * abs(icir) +
                0.3 * (ic_positive_rate - 0.5) * 2 +
                0.2 * abs(rank_ic_mean) * 10
            )

            # 方向惩罚: IC为负的因子降权
            if ic_mean < 0:
                score *= 0.3

            factor_scores[factor_code] = {
                'score': score,
                'ic_mean': ic_mean,
                'icir': icir,
                'coverage': coverage,
                'ic_positive_rate': ic_positive_rate,
            }

        if not factor_scores:
            return []

        # 按综合评分排序
        sorted_factors = sorted(factor_scores.items(), key=lambda x: -x[1]['score'])

        # 筛选: 评分>0 且满足最低条件
        selected = []
        for factor_code, metrics in sorted_factors:
            if metrics['icir'] >= self.MIN_ICIR and metrics['coverage'] >= self.MIN_COVERAGE:
                selected.append(factor_code)
            if len(selected) >= max_factors:
                break

        # 保证最少因子数
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

    def optimize_weights_multi_objective(self,
                                          icir_values: Dict[str, float],
                                          turnover_costs: Dict[str, float] = None,
                                          factor_decay: Dict[str, float] = None,
                                          prev_weights: Dict[str, float] = None,
                                          turnover_penalty: float = 0.3,
                                          decay_penalty: float = 0.1,
                                          stability_penalty: float = 0.2) -> Dict[str, float]:
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
        if turnover_costs:
            tc = np.array([turnover_costs.get(f, 0) for f in factors])
        else:
            tc = np.zeros(n)

        # 因子衰减
        if factor_decay:
            decay = np.array([factor_decay.get(f, 0) for f in factors])
        else:
            decay = np.zeros(n)

        # 上期权重
        if prev_weights:
            w_prev = np.array([prev_weights.get(f, 1.0 / n) for f in factors])
        else:
            w_prev = np.ones(n) / n

        # 只保留正ICIR的因子
        positive_mask = icir > 0
        if not positive_mask.any():
            # 全部ICIR为负，取绝对值最大的
            positive_mask = np.ones(n, dtype=bool)

        # 初始权重: ICIR正比
        abs_icir = np.abs(icir) * positive_mask
        total_icir = abs_icir.sum()
        if total_icir > 0:
            w = abs_icir / total_icir
        else:
            w = np.ones(n) / n

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

        # 清理微小权重
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
        v_clamped = np.clip(v, -1e6, 1e6)
        u = np.sort(v_clamped)[::-1]
        cssv = np.cumsum(u) - 1
        rho_candidates = np.where(u > cssv / np.arange(1, n + 1))[0]

        if len(rho_candidates) == 0:
            # fallback: 均匀分布
            return np.ones(n) / n

        rho = rho_candidates[-1]
        theta = cssv[rho] / (rho + 1.0)

        # 数值稳定性检查: theta过大时回退到均匀分布
        if abs(theta) > 1e8:
            return np.ones(n) / n

        w = np.maximum(v_clamped - theta, 0)

        # 验证投影结果: sum应≈1且无负值
        if abs(np.sum(w) - 1.0) > 1e-6 or np.any(w < -1e-10):
            return np.ones(n) / n

        return w

    # ==================== 3. 因子状态机 ====================

    def update_factor_state(self, factor_code: str,
                             recent_ic: pd.Series,
                             coverage: float = 1.0,
                             trade_date: Optional[date] = None) -> FactorProfile:
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
            if abs(icir) < self.MONITORING_ICIR:
                profile.state = FactorState.MONITORING
                profile.consecutive_low_ic = 1
            elif abs(icir) < self.MIN_ICIR:
                profile.state = FactorState.MONITORING
                profile.consecutive_low_ic = 1

        elif profile.state == FactorState.MONITORING:
            if abs(icir) >= self.RECOVERY_ICIR:
                profile.state = FactorState.ACTIVE
                profile.consecutive_low_ic = 0
            elif abs(icir) < self.MIN_ICIR:
                profile.consecutive_low_ic += 1
                if profile.consecutive_low_ic >= self.CONSECUTIVE_LOW_LIMIT:
                    profile.state = FactorState.INACTIVE
            else:
                profile.consecutive_low_ic = max(0, profile.consecutive_low_ic - 1)

        elif profile.state == FactorState.INACTIVE:
            if abs(icir) >= self.RECOVERY_ICIR:
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

    def get_active_factors(self) -> List[str]:
        """获取所有活跃因子"""
        return [
            f for f, p in self.factor_profiles.items()
            if p.state in (FactorState.ACTIVE, FactorState.MONITORING)
        ]

    def get_factor_weights_by_state(self) -> Dict[str, float]:
        """根据状态分配权重: ACTIVE=1.0, MONITORING=0.5, INACTIVE=0.0"""
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

    def select_orthogonal_subset(self, factor_corr_matrix: pd.DataFrame,
                                   factor_icir: Dict[str, float],
                                   max_factors: int = 30,
                                   corr_threshold: float = 0.6) -> List[str]:
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
            if max_corr > corr_threshold and len(selected) >= 5:
                continue

            # 信息增量过低则跳过
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

    def detect_overfitting(self, train_sharpe: float,
                            test_sharpe: float,
                            n_trials: int = 1,
                            backtest_years: float = 2.0,
                            returns: pd.Series = None) -> Dict[str, Any]:
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
            'train_sharpe': train_sharpe,
            'test_sharpe': test_sharpe,
            'sharpe_decay': 0.0,
            'is_overfit': False,
            'overfitting_score': 0.0,
        }

        # 1. Sharpe衰减率
        if abs(train_sharpe) > 0.01:
            decay = 1 - test_sharpe / train_sharpe
            result['sharpe_decay'] = round(decay, 4)
            # 衰减>50%视为过拟合信号
            if decay > 0.5:
                result['is_overfit'] = True
                result['overfitting_score'] += 0.4

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

                result['dsr'] = round(dsr, 4)
                result['expected_max_sharpe'] = round(expected_max_sr, 2)
                if dsr < 0.95:
                    result['is_overfit'] = True
                    result['overfitting_score'] += 0.3 * (1 - dsr)
            except Exception:
                pass

        # 3. 蒙特卡洛置换检验 (如果有收益率数据)
        if returns is not None and len(returns) > 60:
            mc_result = self._permutation_test(returns, n_permutations=500)
            result['permutation_p_value'] = mc_result['p_value']
            if mc_result['p_value'] > 0.05:
                result['is_overfit'] = True
                result['overfitting_score'] += 0.3

        # 综合评分
        result['overfitting_score'] = round(result['overfitting_score'], 4)

        logger.info(
            "Overfitting detection completed",
            extra={
                "train_sharpe": train_sharpe,
                "test_sharpe": test_sharpe,
                "is_overfit": result['is_overfit'],
                "overfitting_score": result['overfitting_score'],
            },
        )

        return result

    def _permutation_test(self, returns: pd.Series,
                           n_permutations: int = 500,
                           block_size: int = 5) -> Dict[str, float]:
        """块置换检验"""
        actual_sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        n = len(returns)
        permuted_sharpes = []

        for _ in range(n_permutations):
            n_blocks = n // block_size
            block_indices = np.arange(n_blocks)
            np.random.shuffle(block_indices)
            permuted = np.concatenate([
                returns.iloc[i * block_size:(i + 1) * block_size].values
                for i in block_indices
            ])
            remainder = n % block_size
            if remainder > 0:
                permuted = np.concatenate([permuted, returns.iloc[-remainder:].values])
            perm_sharpe = permuted.mean() / permuted.std() * np.sqrt(252) if permuted.std() > 0 else 0
            permuted_sharpes.append(perm_sharpe)

        p_value = sum(1 for s in permuted_sharpes if s >= actual_sharpe) / n_permutations
        return {'p_value': p_value, 'actual_sharpe': actual_sharpe}

    # ==================== 6. 因子衰减分析 ====================

    def analyze_factor_decay(self, ic_series: pd.Series,
                              half_life_init: int = 60) -> Dict[str, Any]:
        """
        分析因子IC衰减
        用指数衰减模型拟合IC时间序列: IC(t) = IC_0 * exp(-t/τ) + noise
        估计半衰期τ_{1/2} = τ * ln(2)
        """
        ic = ic_series.dropna()
        if len(ic) < 20:
            return {'half_life': np.nan, 'is_decaying': False}

        # 拟合指数衰减: IC(t) = a * exp(-b*t) + c
        t = np.arange(len(ic))
        ic_values = ic.values

        try:
            from scipy.optimize import curve_fit

            def exp_decay(t, a, b, c):
                return a * np.exp(-b * t) + c

            popt, _ = curve_fit(
                exp_decay, t, ic_values,
                p0=[ic_values[0], 0.01, ic_values.mean()],
                maxfev=5000,
            )
            a, b, c = popt

            if b > 0:
                half_life = np.log(2) / b
            else:
                half_life = np.inf

            is_decaying = b > 0.005 and half_life < len(ic) * 0.8

            return {
                'half_life': round(half_life, 1),
                'decay_rate': round(b, 6),
                'initial_ic': round(a, 4),
                'steady_state_ic': round(c, 4),
                'is_decaying': is_decaying,
            }
        except Exception:
            # 回退: 用前后半段IC均值比较
            mid = len(ic) // 2
            first_half_ic = ic.iloc[:mid].mean()
            second_half_ic = ic.iloc[mid:].mean()
            is_decaying = second_half_ic < first_half_ic * 0.7

            return {
                'half_life': np.nan,
                'first_half_ic': round(first_half_ic, 4),
                'second_half_ic': round(second_half_ic, 4),
                'is_decaying': is_decaying,
            }

    # ==================== 7. 批量更新因子画像 ====================

    def batch_update_profiles(self, ic_history: pd.DataFrame,
                               coverage_data: Optional[Dict[str, float]] = None,
                               trade_date: Optional[date] = None) -> Dict[str, FactorProfile]:
        """
        批量更新所有因子画像
        """
        if ic_history.empty:
            return self.factor_profiles

        for factor_code in ic_history['factor_code'].unique():
            f_ic = ic_history[ic_history['factor_code'] == factor_code]['ic']
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
