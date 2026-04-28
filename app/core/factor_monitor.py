"""
因子衰减与漂移监控模块
实现GPT设计11.1节+16.6节: 监控IC漂移、因子分布变化、模块相关性变化
核心: 当因子失效时及时发现并告警，避免持续使用已失效的alpha
"""

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from app.core.logging import logger


class FactorMonitor:
    """因子监控器 - GPT设计11.1节+16.6节"""

    # 告警阈值
    DEFAULT_THRESHOLDS = {
        "ic_min": 0.02,  # IC均值最低阈值
        "ir_min": 0.5,  # IR最低阈值
        "ic_t_stat_min": 2.0,  # IC t统计量最低阈值
        "psi_max": 0.25,  # PSI最大阈值 (>0.25表示显著分布变化)
        "ks_p_value_min": 0.05,  # KS检验p值最低阈值
        "correlation_max": 0.85,  # 模块间最大相关性
        "coverage_min": 0.5,  # 最低覆盖率
    }

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()

    # ==================== 滚动IC ====================

    def rolling_ic(
        self, factor_values: pd.Series, forward_returns: pd.Series, window: int = 60, method: str = "spearman"
    ) -> pd.Series:
        """
        滚动IC (Rank IC或Pearson IC)

        Args:
            factor_values: 因子值, index=trade_date或(trade_date, ts_code)
            forward_returns: 前瞻收益, 同index
            window: 滚动窗口(交易日)
            method: 'spearman'(Rank IC) 或 'pearson'

        Returns:
            滚动IC序列
        """
        if len(factor_values) != len(forward_returns):
            # 尝试对齐
            common_idx = factor_values.index.intersection(forward_returns.index)
            factor_values = factor_values.loc[common_idx]
            forward_returns = forward_returns.loc[common_idx]

        if len(factor_values) < window:
            return pd.Series(dtype=float)

        # 按日期计算截面IC
        if isinstance(factor_values.index, pd.MultiIndex):
            # (trade_date, ts_code) 格式
            df = pd.DataFrame({"factor": factor_values, "return": forward_returns})
            ic_series = df.groupby(level=0).apply(
                lambda x: x["factor"].corr(x["return"], method=method) if len(x.dropna()) > 10 else np.nan
            )
            # 滚动均值
            return ic_series.rolling(window, min_periods=window // 2).mean()
        # 时间序列格式: 直接计算滚动相关
        aligned = pd.DataFrame({"factor": factor_values, "return": forward_returns}).dropna()
        if len(aligned) < window:
            return pd.Series(dtype=float)

        ic_list = []
        dates = []
        for i in range(window, len(aligned) + 1):
            window_data = aligned.iloc[i - window : i]
            if method == "spearman":
                ic = window_data["factor"].corr(window_data["return"], method="spearman")
            else:
                ic = window_data["factor"].corr(window_data["return"])
            ic_list.append(ic)
            dates.append(aligned.index[i - 1])

        return pd.Series(ic_list, index=dates)

    # ==================== IC漂移检测 ====================

    def ic_drift(self, ic_series: pd.Series, window: int = 60, min_periods: int = 20) -> dict[str, float]:
        """
        IC漂移检测 (GPT设计16.6节)

        比较近期IC与长期IC的差异，检测因子是否正在失效

        Args:
            ic_series: IC时间序列
            window: 近期窗口

        Returns:
            {ic_recent, ic_long, drift, is_decaying}
        """
        ic_series = ic_series.dropna()
        if len(ic_series) < min_periods * 2:
            return {"ic_recent": np.nan, "ic_long": np.nan, "drift": np.nan, "is_decaying": False}

        ic_long = ic_series.mean()
        ic_recent = ic_series.tail(window).mean()

        drift = ic_recent - ic_long

        # 衰减判定: 近期IC显著低于长期IC
        is_decaying = drift < -0.02 and abs(ic_recent) < abs(ic_long) * 0.5

        return {
            "ic_recent": round(ic_recent, 4),
            "ic_long": round(ic_long, 4),
            "drift": round(drift, 4),
            "is_decaying": is_decaying,
        }

    # ==================== PSI (分布漂移) ====================

    def psi(self, current_dist: pd.Series, reference_dist: pd.Series, n_bins: int = 10) -> float:
        """
        PSI (Population Stability Index) 分布漂移检测

        PSI < 0.10: 无显著变化
        0.10 <= PSI < 0.25: 中等变化, 需关注
        PSI >= 0.25: 显著变化, 需行动

        Args:
            current_dist: 当前分布 (因子值)
            reference_dist: 参考分布 (如训练期因子值)
            n_bins: 分箱数

        Returns:
            PSI值
        """
        current = current_dist.dropna()
        reference = reference_dist.dropna()

        if len(current) < 30 or len(reference) < 30:
            return 0.0

        # 用参考分布的分位数作为分箱边界
        bin_edges = np.quantile(reference, np.linspace(0, 1, n_bins + 1))
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf

        # 计算各bin占比
        ref_counts = np.histogram(reference, bins=bin_edges)[0]
        cur_counts = np.histogram(current, bins=bin_edges)[0]

        ref_pct = ref_counts / len(reference)
        cur_pct = cur_counts / len(current)

        # PSI = Σ (cur_i - ref_i) * ln(cur_i / ref_i)
        psi_value = 0.0
        for i in range(n_bins):
            if ref_pct[i] > 0 and cur_pct[i] > 0:
                psi_value += (cur_pct[i] - ref_pct[i]) * np.log(cur_pct[i] / ref_pct[i])

        return psi_value

    # ==================== KS检验 ====================

    def rolling_ks(self, factor_values_t: pd.Series, factor_values_ref: pd.Series) -> dict[str, float]:
        """
        滚动KS检验 (GPT设计16.6节)

        检验当前因子分布与参考分布是否有显著差异

        Args:
            factor_values_t: 当前因子值
            factor_values_ref: 参考因子值

        Returns:
            {ks_statistic, p_value, is_significant}
        """
        current = factor_values_t.dropna()
        reference = factor_values_ref.dropna()

        if len(current) < 30 or len(reference) < 30:
            return {"ks_statistic": 0, "p_value": 1.0, "is_significant": False}

        ks_stat, p_value = sp_stats.ks_2samp(current, reference)

        return {
            "ks_statistic": round(ks_stat, 4),
            "p_value": round(p_value, 4),
            "is_significant": p_value < self.thresholds["ks_p_value_min"],
        }

    # ==================== 模块相关性矩阵 ====================

    def module_correlation_matrix(self, module_scores: pd.DataFrame, window: int = 60) -> pd.DataFrame:
        """
        模块间滚动相关性矩阵 (GPT设计11.1节)

        高相关性意味着模块间信息重复，需要权重收缩

        Args:
            module_scores: 模块分数, columns=模块名, index=trade_date
            window: 滚动窗口

        Returns:
            相关性矩阵
        """
        if module_scores.empty or len(module_scores) < window:
            return module_scores.corr()

        recent = module_scores.tail(window)
        return recent.corr()

    # ==================== 综合健康检查 ====================

    def check_health(
        self,
        ic_series: pd.Series | None = None,
        factor_values_current: pd.Series | None = None,
        factor_values_reference: pd.Series | None = None,
        module_scores: pd.DataFrame | None = None,
        module_name: str = "unknown",
    ) -> dict[str, Any]:
        """
        综合健康检查，返回告警列表

        Args:
            ic_series: IC时间序列
            factor_values_current: 当前因子值
            factor_values_reference: 参考因子值
            module_scores: 模块分数DataFrame
            module_name: 模块名

        Returns:
            {is_healthy, alerts: List[str], details: Dict}
        """
        alerts = []
        details = {"module": module_name}

        # 1. IC检查
        if ic_series is not None and not ic_series.empty:
            ic_clean = ic_series.dropna()
            if len(ic_clean) > 20:
                ic_mean = ic_clean.mean()
                ic_std = ic_clean.std()
                ir = ic_mean / ic_std if ic_std > 0 else 0
                t_stat = ic_mean / (ic_std / np.sqrt(len(ic_clean))) if ic_std > 0 else 0

                details["ic_mean"] = round(ic_mean, 4)
                details["ir"] = round(ir, 4)
                details["ic_t_stat"] = round(t_stat, 4)

                if abs(ic_mean) < self.thresholds["ic_min"]:
                    alerts.append(f"IC均值{ic_mean:.4f}低于阈值{self.thresholds['ic_min']}")

                if abs(ir) < self.thresholds["ir_min"]:
                    alerts.append(f"IR{ir:.4f}低于阈值{self.thresholds['ir_min']}")

                if abs(t_stat) < self.thresholds["ic_t_stat_min"]:
                    alerts.append(f"IC t统计量{t_stat:.4f}低于阈值{self.thresholds['ic_t_stat_min']}")

                # IC漂移
                drift_result = self.ic_drift(ic_clean)
                details["ic_drift"] = drift_result
                if drift_result.get("is_decaying", False):
                    alerts.append(
                        f"IC衰减: 近期IC={drift_result['ic_recent']:.4f}, 长期IC={drift_result['ic_long']:.4f}"
                    )

        # 2. PSI检查
        if factor_values_current is not None and factor_values_reference is not None:
            psi_val = self.psi(factor_values_current, factor_values_reference)
            details["psi"] = round(psi_val, 4)

            if psi_val >= self.thresholds["psi_max"]:
                alerts.append(f"PSI={psi_val:.4f}超过阈值{self.thresholds['psi_max']}, 分布显著漂移")
            elif psi_val >= 0.10:
                alerts.append(f"PSI={psi_val:.4f}中等漂移, 需关注")

        # 3. KS检验
        if factor_values_current is not None and factor_values_reference is not None:
            ks_result = self.rolling_ks(factor_values_current, factor_values_reference)
            details["ks_test"] = ks_result
            if ks_result.get("is_significant", False):
                alerts.append(f"KS检验显著: stat={ks_result['ks_statistic']:.4f}, p={ks_result['p_value']:.4f}")

        # 4. 模块相关性检查
        if module_scores is not None and module_scores.shape[1] >= 2:
            corr = self.module_correlation_matrix(module_scores)
            details["correlation_matrix"] = corr.round(3).to_dict()

            # 检查高相关对
            modules = list(corr.columns)
            for i in range(len(modules)):
                for j in range(i + 1, len(modules)):
                    c = abs(corr.iloc[i, j])
                    if c > self.thresholds["correlation_max"]:
                        alerts.append(f"模块{modules[i]}与{modules[j]}高度相关: {c:.4f}")

        is_healthy = len(alerts) == 0

        if not is_healthy:
            logger.warning(
                f"Factor health check: {module_name} has {len(alerts)} alerts",
                extra={"module": module_name, "alerts": alerts},
            )

        return {
            "is_healthy": is_healthy,
            "alerts": alerts,
            "details": details,
        }

    # ==================== 批量健康检查 ====================

    def check_all_modules(
        self, module_ic_map: dict[str, pd.Series], module_scores: pd.DataFrame | None = None
    ) -> dict[str, dict]:
        """
        批量检查所有模块健康状态

        Args:
            module_ic_map: {module_name: ic_series}
            module_scores: 模块分数DataFrame (可选)

        Returns:
            {module_name: health_check_result}
        """
        results = {}
        for module_name, ic_series in module_ic_map.items():
            results[module_name] = self.check_health(
                ic_series=ic_series,
                module_scores=module_scores,
                module_name=module_name,
            )

        # 汇总
        n_healthy = sum(1 for r in results.values() if r["is_healthy"])
        n_total = len(results)

        logger.info(
            "All modules health check completed",
            extra={
                "n_healthy": n_healthy,
                "n_total": n_total,
                "unhealthy_modules": [name for name, r in results.items() if not r["is_healthy"]],
            },
        )

        return results
