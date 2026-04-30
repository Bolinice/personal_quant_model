"""
回测引擎性能优化模块
提供向量化计算、并行回测、结果缓存等性能优化功能
"""

from __future__ import annotations

import hashlib
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
import pandas as pd

from app.core.logging import logger

if TYPE_CHECKING:
    from datetime import date


@dataclass
class BacktestCache:
    """回测缓存配置"""

    enabled: bool = True
    cache_dir: str = ".cache/backtest"
    max_cache_size: int = 100  # 最多缓存100个回测结果


class VectorizedBacktestEngine:
    """
    向量化回测引擎

    核心优化：
    1. 向量化净值计算：避免逐日循环
    2. 向量化持仓更新：批量处理调仓
    3. 向量化成本计算：矩阵运算替代循环
    """

    def __init__(self, cache_config: BacktestCache | None = None):
        self.cache_config = cache_config or BacktestCache()
        if self.cache_config.enabled:
            Path(self.cache_config.cache_dir).mkdir(parents=True, exist_ok=True)

    # ==================== 1. 向量化净值计算 ====================

    def calc_nav_vectorized(
        self,
        positions_df: pd.DataFrame,
        prices_df: pd.DataFrame,
        cash_series: pd.Series,
        initial_capital: float,
    ) -> pd.DataFrame:
        """
        向量化计算净值序列

        Args:
            positions_df: 持仓矩阵 (date x stock)，值为持仓股数
            prices_df: 价格矩阵 (date x stock)
            cash_series: 现金序列 (date)
            initial_capital: 初始资金

        Returns:
            净值DataFrame，包含 nav, total_value, cash, position_value
        """
        # 向量化计算持仓市值：positions * prices
        position_values = (positions_df * prices_df).sum(axis=1)

        # 总资产 = 持仓市值 + 现金
        total_values = position_values + cash_series

        # 净值 = 总资产 / 初始资金
        nav = total_values / initial_capital

        result = pd.DataFrame(
            {
                "nav": nav,
                "total_value": total_values,
                "cash": cash_series,
                "position_value": position_values,
            },
            index=positions_df.index,
        )

        logger.info(f"Vectorized NAV calculation completed for {len(result)} days")
        return result

    def calc_returns_vectorized(self, nav_series: pd.Series) -> pd.DataFrame:
        """
        向量化计算收益率序列

        Args:
            nav_series: 净值序列

        Returns:
            收益率DataFrame，包含 daily_return, cumulative_return
        """
        # 日收益率
        daily_returns = nav_series.pct_change().fillna(0)

        # 累计收益率
        cumulative_returns = (1 + daily_returns).cumprod() - 1

        result = pd.DataFrame(
            {
                "daily_return": daily_returns,
                "cumulative_return": cumulative_returns,
            },
            index=nav_series.index,
        )

        return result

    # ==================== 2. 向量化持仓更新 ====================

    def update_positions_vectorized(
        self,
        current_positions: pd.Series,
        target_weights: pd.Series,
        prices: pd.Series,
        total_value: float,
        lot_size: int = 100,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        向量化计算持仓调整

        Args:
            current_positions: 当前持仓股数 (stock)
            target_weights: 目标权重 (stock)
            prices: 当前价格 (stock)
            total_value: 总资产
            lot_size: 交易单位（A股100股）

        Returns:
            (新持仓股数, 买入股数, 卖出股数)
        """
        # 目标持仓市值
        target_values = target_weights * total_value

        # 目标持仓股数（向下取整到交易单位）
        target_shares = (target_values / prices).fillna(0)
        target_shares = (target_shares // lot_size) * lot_size

        # 当前持仓股数（对齐索引）
        current_shares = current_positions.reindex(target_shares.index, fill_value=0)

        # 计算买卖数量
        delta_shares = target_shares - current_shares
        buy_shares = delta_shares.clip(lower=0)
        sell_shares = (-delta_shares).clip(lower=0)

        return target_shares, buy_shares, sell_shares

    # ==================== 3. 向量化成本计算 ====================

    def calc_transaction_costs_vectorized(
        self,
        trade_amounts: pd.Series,
        trade_directions: pd.Series,
        commission_rate: float = 0.00025,
        stamp_tax_rate: float = 0.001,
        slippage_rate: float = 0.001,
        min_commission: float = 5.0,
    ) -> pd.DataFrame:
        """
        向量化计算交易成本

        Args:
            trade_amounts: 交易金额序列 (stock)
            trade_directions: 交易方向序列 (stock)，1=买入，-1=卖出
            commission_rate: 佣金费率
            stamp_tax_rate: 印花税率
            slippage_rate: 滑点率
            min_commission: 最低佣金

        Returns:
            成本DataFrame，包含 commission, stamp_tax, slippage, total_cost
        """
        # 佣金（买卖双向）
        commissions = np.maximum(trade_amounts * commission_rate, min_commission)

        # 印花税（仅卖出）
        stamp_taxes = np.where(trade_directions < 0, trade_amounts * stamp_tax_rate, 0)

        # 滑点（买卖双向）
        slippages = trade_amounts * slippage_rate

        # 总成本
        total_costs = commissions + stamp_taxes + slippages

        result = pd.DataFrame(
            {
                "commission": commissions,
                "stamp_tax": stamp_taxes,
                "slippage": slippages,
                "total_cost": total_costs,
            },
            index=trade_amounts.index,
        )

        return result

    # ==================== 4. 向量化指标计算 ====================

    def calc_metrics_vectorized(self, returns: pd.Series, benchmark_returns: pd.Series | None = None) -> dict[str, float]:
        """
        向量化计算回测指标

        Args:
            returns: 策略收益率序列
            benchmark_returns: 基准收益率序列

        Returns:
            指标字典
        """
        # 基础统计
        total_return = (1 + returns).prod() - 1
        annual_return = (1 + total_return) ** (252 / len(returns)) - 1
        volatility = returns.std() * np.sqrt(252)

        # 夏普比率
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0

        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = drawdowns.min()

        # 卡玛比率
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 下行波动率
        downside_returns = returns[returns < 0]
        downside_volatility = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0

        # 索提诺比率
        sortino_ratio = annual_return / downside_volatility if downside_volatility > 0 else 0

        # 胜率
        win_rate = (returns > 0).sum() / len(returns)

        metrics = {
            "total_return": float(total_return),
            "annual_return": float(annual_return),
            "volatility": float(volatility),
            "sharpe_ratio": float(sharpe_ratio),
            "max_drawdown": float(max_drawdown),
            "calmar_ratio": float(calmar_ratio),
            "downside_volatility": float(downside_volatility),
            "sortino_ratio": float(sortino_ratio),
            "win_rate": float(win_rate),
        }

        # 如果有基准，计算超额收益指标
        if benchmark_returns is not None:
            excess_returns = returns - benchmark_returns
            tracking_error = excess_returns.std() * np.sqrt(252)
            information_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0

            metrics.update(
                {
                    "tracking_error": float(tracking_error),
                    "information_ratio": float(information_ratio),
                    "excess_return": float(excess_returns.sum()),
                }
            )

        return metrics

    # ==================== 5. 回测缓存 ====================

    def _get_cache_key(self, config: dict) -> str:
        """生成缓存键"""
        config_str = str(sorted(config.items()))
        return hashlib.md5(config_str.encode()).hexdigest()

    def get_cached_result(self, config: dict) -> dict | None:
        """获取缓存的回测结果"""
        if not self.cache_config.enabled:
            return None

        cache_key = self._get_cache_key(config)
        cache_file = Path(self.cache_config.cache_dir) / f"{cache_key}.pkl"

        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    result = pickle.load(f)
                logger.info(f"Loaded cached backtest result: {cache_key}")
                return result
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                return None

        return None

    def save_cached_result(self, config: dict, result: dict) -> None:
        """保存回测结果到缓存"""
        if not self.cache_config.enabled:
            return

        cache_key = self._get_cache_key(config)
        cache_file = Path(self.cache_config.cache_dir) / f"{cache_key}.pkl"

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(result, f)
            logger.info(f"Saved backtest result to cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def clear_cache(self) -> None:
        """清空缓存"""
        cache_dir = Path(self.cache_config.cache_dir)
        if cache_dir.exists():
            for cache_file in cache_dir.glob("*.pkl"):
                cache_file.unlink()
            logger.info("Cleared backtest cache")


class ParallelBacktestRunner:
    """
    并行回测运行器

    支持多策略并行回测，充分利用多核CPU
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def run_parallel(
        self,
        backtest_func: Callable,
        configs: list[dict],
        show_progress: bool = True,
    ) -> list[dict]:
        """
        并行运行多个回测

        Args:
            backtest_func: 回测函数，接受config参数，返回结果字典
            configs: 配置列表
            show_progress: 是否显示进度

        Returns:
            结果列表
        """
        results = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_config = {executor.submit(backtest_func, config): config for config in configs}

            # 收集结果
            completed = 0
            total = len(configs)

            for future in as_completed(future_to_config):
                config = future_to_config[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    if show_progress:
                        logger.info(f"Backtest progress: {completed}/{total} ({completed/total:.1%})")

                except Exception as e:
                    logger.error(f"Backtest failed for config {config}: {e}")
                    results.append({"error": str(e), "config": config})

        logger.info(f"Parallel backtest completed: {len(results)} results")
        return results

    def run_parameter_sweep(
        self,
        backtest_func: Callable,
        base_config: dict,
        param_grid: dict[str, list],
    ) -> pd.DataFrame:
        """
        参数扫描

        Args:
            backtest_func: 回测函数
            base_config: 基础配置
            param_grid: 参数网格，如 {"param1": [1, 2, 3], "param2": [0.1, 0.2]}

        Returns:
            结果DataFrame
        """
        # 生成所有参数组合
        import itertools

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))

        # 生成配置列表
        configs = []
        for combination in param_combinations:
            config = base_config.copy()
            for name, value in zip(param_names, combination):
                config[name] = value
            configs.append(config)

        logger.info(f"Parameter sweep: {len(configs)} combinations")

        # 并行运行
        results = self.run_parallel(backtest_func, configs)

        # 转换为DataFrame
        results_df = pd.DataFrame(results)

        # 添加参数列
        for i, name in enumerate(param_names):
            results_df[name] = [combo[i] for combo in param_combinations]

        return results_df


# ==================== 辅助函数 ====================


def benchmark_backtest_speed(
    backtest_func: Callable,
    config: dict,
    n_runs: int = 10,
) -> dict[str, float]:
    """
    基准测试回测速度

    Args:
        backtest_func: 回测函数
        config: 配置
        n_runs: 运行次数

    Returns:
        性能指标字典
    """
    import time

    times = []

    for i in range(n_runs):
        start = time.time()
        backtest_func(config)
        elapsed = time.time() - start
        times.append(elapsed)

        logger.info(f"Run {i+1}/{n_runs}: {elapsed:.2f}s")

    return {
        "mean_time": np.mean(times),
        "std_time": np.std(times),
        "min_time": np.min(times),
        "max_time": np.max(times),
    }
