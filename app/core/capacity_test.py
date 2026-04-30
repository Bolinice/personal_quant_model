"""
回测容量测试 — 评估策略在不同资金规模下的表现

功能:
  1. 多资金规模回测：1M/10M/100M/500M/1B
  2. 容量衰减曲线：收益率 vs 资金规模
  3. 最优容量估算：收益率衰减到80%时的资金规模
  4. 流动性冲击分析：大单对收益的影响
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from app.core.backtest_engine import ABShareBacktestEngine

logger = logging.getLogger(__name__)


@dataclass
class CapacityTestResult:
    """容量测试结果"""

    capital_levels: list[float]  # 资金规模列表
    returns: list[float]  # 年化收益率
    sharpe_ratios: list[float]  # 夏普比率
    turnover_rates: list[float]  # 换手率
    avg_slippage_bps: list[float]  # 平均滑点(bps)
    optimal_capacity: float  # 最优容量(收益衰减到80%时)
    capacity_decay_rate: float  # 容量衰减率(%/100M)


class CapacityTester:
    """回测容量测试器"""

    # 默认测试资金规模（元）
    DEFAULT_CAPITAL_LEVELS: list[float] = [
        1_000_000.0,  # 1M
        10_000_000.0,  # 10M
        50_000_000.0,  # 50M
        100_000_000.0,  # 100M
        500_000_000.0,  # 500M
        1_000_000_000.0,  # 1B
    ]

    def __init__(self, backtest_engine: ABShareBacktestEngine):
        self.backtest_engine = backtest_engine

    def run_capacity_test(
        self,
        signal_generator: Callable[[date, list[str], Any], dict[str, float]],
        universe: list[str],
        start_date: date,
        end_date: date,
        price_data: dict[tuple[str, date], dict[str, Any]] | None = None,
        capital_levels: list[float] | None = None,
    ) -> CapacityTestResult:
        """
        运行容量测试

        Args:
            signal_generator: 信号生成器
            universe: 股票池
            start_date: 开始日期
            end_date: 结束日期
            price_data: 行情数据
            capital_levels: 测试资金规模列表

        Returns:
            CapacityTestResult: 容量测试结果
        """
        if capital_levels is None:
            capital_levels = self.DEFAULT_CAPITAL_LEVELS.copy()

        logger.info("开始容量测试: %d个资金规模", len(capital_levels))

        results = []
        for capital in capital_levels:
            logger.info("测试资金规模: %.0fM", capital / 1_000_000)

            # 运行回测
            backtest_result = self.backtest_engine.run_backtest(
                signal_generator=signal_generator,
                universe=universe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=capital,
                price_data=price_data,
            )

            if backtest_result and "metrics" in backtest_result:
                metrics = backtest_result["metrics"]
                results.append(
                    {
                        "capital": capital,
                        "annual_return": metrics.get("annual_return", 0.0),
                        "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                        "turnover_rate": metrics.get("turnover_rate", 0.0),
                        "avg_slippage_bps": self._calc_avg_slippage(backtest_result),
                    }
                )
            else:
                logger.warning("回测失败: capital=%.0fM", capital / 1_000_000)
                results.append(
                    {
                        "capital": capital,
                        "annual_return": 0.0,
                        "sharpe_ratio": 0.0,
                        "turnover_rate": 0.0,
                        "avg_slippage_bps": 0.0,
                    }
                )

        # 计算最优容量和衰减率
        optimal_capacity, decay_rate = self._calc_optimal_capacity(results)

        return CapacityTestResult(
            capital_levels=[r["capital"] for r in results],
            returns=[r["annual_return"] for r in results],
            sharpe_ratios=[r["sharpe_ratio"] for r in results],
            turnover_rates=[r["turnover_rate"] for r in results],
            avg_slippage_bps=[r["avg_slippage_bps"] for r in results],
            optimal_capacity=optimal_capacity,
            capacity_decay_rate=decay_rate,
        )

    def _calc_avg_slippage(self, backtest_result: dict[str, Any]) -> float:
        """计算平均滑点(bps)"""
        trades = backtest_result.get("trades", [])
        if not trades:
            return 0.0

        total_slippage_bps = 0.0
        count = 0

        for trade in trades:
            cost_detail = trade.get("cost_detail", {})
            slippage = cost_detail.get("slippage", 0.0)
            amount = trade.get("amount", 0.0)
            if amount > 0:
                slippage_bps = (slippage / amount) * 10000
                total_slippage_bps += slippage_bps
                count += 1

        return total_slippage_bps / count if count > 0 else 0.0

    def _calc_optimal_capacity(self, results: list[dict[str, Any]]) -> tuple[float, float]:
        """
        计算最优容量和衰减率

        最优容量定义: 年化收益率衰减到基准(最小资金规模)的80%时的资金规模
        衰减率: 每增加100M资金，收益率下降的百分点
        """
        if len(results) < 2:
            return 0.0, 0.0

        # 基准收益率（最小资金规模）
        base_return = results[0]["annual_return"]
        if base_return <= 0:
            return 0.0, 0.0

        # 找到收益率衰减到80%的点
        target_return = base_return * 0.8
        optimal_capacity = results[-1]["capital"]  # 默认最大值

        for i, r in enumerate(results):
            if r["annual_return"] <= target_return:
                if i > 0:
                    # 线性插值
                    prev = results[i - 1]
                    ratio = (target_return - r["annual_return"]) / (prev["annual_return"] - r["annual_return"])
                    optimal_capacity = r["capital"] + ratio * (prev["capital"] - r["capital"])
                else:
                    optimal_capacity = r["capital"]
                break

        # 计算衰减率：拟合线性回归
        capitals = np.array([r["capital"] / 100_000_000 for r in results])  # 单位: 100M
        returns = np.array([r["annual_return"] for r in results])

        if len(capitals) >= 2:
            # 简单线性回归: return = a + b * capital
            coef = np.polyfit(capitals, returns, 1)
            decay_rate = -coef[0] * 100  # 转换为百分点，取负值表示衰减
        else:
            decay_rate = 0.0

        logger.info("最优容量: %.0fM, 衰减率: %.2f%%/100M", optimal_capacity / 1_000_000, decay_rate)

        return optimal_capacity, decay_rate

    def print_report(self, result: CapacityTestResult) -> None:
        """打印容量测试报告"""
        print("\n" + "=" * 80)
        print("回测容量测试报告")
        print("=" * 80)

        print(f"\n{'资金规模':<12} {'年化收益':<12} {'夏普比率':<12} {'换手率':<12} {'平均滑点(bps)':<12}")
        print("-" * 80)

        for i in range(len(result.capital_levels)):
            capital_m = result.capital_levels[i] / 1_000_000
            print(
                f"{capital_m:>10.0f}M  "
                f"{result.returns[i]:>10.2%}  "
                f"{result.sharpe_ratios[i]:>10.2f}  "
                f"{result.turnover_rates[i]:>10.2%}  "
                f"{result.avg_slippage_bps[i]:>10.2f}"
            )

        print("-" * 80)
        print(f"最优容量: {result.optimal_capacity / 1_000_000:.0f}M")
        print(f"容量衰减率: {result.capacity_decay_rate:.2f}%/100M")
        print("=" * 80 + "\n")
