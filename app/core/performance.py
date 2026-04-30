"""
性能监控工具
提供装饰器和上下文管理器，用于追踪关键路径耗时
"""

import functools
import time
from contextlib import contextmanager
from typing import Any, Callable

from app.core.logging import logger


class PerformanceMonitor:
    """性能监控器 - 收集和分析性能指标"""

    def __init__(self):
        self.metrics: dict[str, list[float]] = {}
        self.call_counts: dict[str, int] = {}

    def record(self, name: str, duration_ms: float):
        """记录一次性能指标"""
        if name not in self.metrics:
            self.metrics[name] = []
            self.call_counts[name] = 0

        self.metrics[name].append(duration_ms)
        self.call_counts[name] += 1

    def get_stats(self, name: str) -> dict[str, float]:
        """获取指标统计信息"""
        if name not in self.metrics or not self.metrics[name]:
            return {}

        durations = self.metrics[name]
        return {
            "count": self.call_counts[name],
            "total_ms": sum(durations),
            "avg_ms": sum(durations) / len(durations),
            "min_ms": min(durations),
            "max_ms": max(durations),
            "p50_ms": sorted(durations)[len(durations) // 2],
            "p95_ms": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0],
            "p99_ms": sorted(durations)[int(len(durations) * 0.99)] if len(durations) > 1 else durations[0],
        }

    def get_summary(self) -> dict[str, dict[str, float]]:
        """获取所有指标的汇总"""
        return {name: self.get_stats(name) for name in self.metrics.keys()}

    def print_summary(self, top_n: int = 20):
        """打印性能汇总（按总耗时排序）"""
        summary = self.get_summary()
        if not summary:
            logger.info("无性能数据")
            return

        # 按总耗时排序
        sorted_items = sorted(summary.items(), key=lambda x: x[1].get("total_ms", 0), reverse=True)

        logger.info("=" * 80)
        logger.info("性能监控汇总 (Top %d)", top_n)
        logger.info("=" * 80)
        logger.info(
            "%-40s %8s %10s %10s %10s %10s",
            "名称",
            "调用次数",
            "总耗时(ms)",
            "平均(ms)",
            "P95(ms)",
            "P99(ms)",
        )
        logger.info("-" * 80)

        for name, stats in sorted_items[:top_n]:
            logger.info(
                "%-40s %8d %10.1f %10.1f %10.1f %10.1f",
                name[:40],
                stats["count"],
                stats["total_ms"],
                stats["avg_ms"],
                stats["p95_ms"],
                stats["p99_ms"],
            )

        logger.info("=" * 80)

    def reset(self):
        """重置所有指标"""
        self.metrics.clear()
        self.call_counts.clear()


# 全局性能监控器实例
_global_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    return _global_monitor


@contextmanager
def timer(name: str, log_threshold_ms: float = 0, monitor: PerformanceMonitor | None = None):
    """
    性能计时上下文管理器

    Args:
        name: 计时名称
        log_threshold_ms: 日志阈值，超过此值才记录日志（0表示总是记录）
        monitor: 性能监控器实例，None则使用全局实例

    Example:
        with timer("calculate_factors"):
            result = calculate_factors(df)
    """
    if monitor is None:
        monitor = _global_monitor

    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        monitor.record(name, duration_ms)

        if log_threshold_ms == 0 or duration_ms >= log_threshold_ms:
            logger.info(f"⏱️  {name}: {duration_ms:.1f}ms")


def timed(name: str | None = None, log_threshold_ms: float = 0, monitor: PerformanceMonitor | None = None):
    """
    性能计时装饰器

    Args:
        name: 计时名称，None则使用函数名
        log_threshold_ms: 日志阈值，超过此值才记录日志（0表示总是记录）
        monitor: 性能监控器实例，None则使用全局实例

    Example:
        @timed("my_function")
        def my_function():
            pass
    """

    def decorator(func: Callable) -> Callable:
        timer_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with timer(timer_name, log_threshold_ms, monitor):
                return func(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def batch_timer(name: str, batch_size: int, monitor: PerformanceMonitor | None = None):
    """
    批量操作计时器 - 自动计算单项平均耗时

    Args:
        name: 计时名称
        batch_size: 批量大小
        monitor: 性能监控器实例

    Example:
        with batch_timer("process_stocks", len(stocks)):
            for stock in stocks:
                process(stock)
    """
    if monitor is None:
        monitor = _global_monitor

    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        monitor.record(name, duration_ms)

        avg_ms = duration_ms / batch_size if batch_size > 0 else 0
        logger.info(f"⏱️  {name}: {duration_ms:.1f}ms total, {avg_ms:.2f}ms/item ({batch_size} items)")


class PerformanceProfiler:
    """性能分析器 - 用于分析热点函数"""

    def __init__(self):
        self.enabled = False
        self.profiler = None

    def start(self):
        """启动性能分析"""
        try:
            import cProfile

            self.profiler = cProfile.Profile()
            self.profiler.enable()
            self.enabled = True
            logger.info("性能分析器已启动")
        except ImportError:
            logger.warning("cProfile不可用，跳过性能分析")

    def stop(self, output_file: str | None = None):
        """停止性能分析并输出结果"""
        if not self.enabled or self.profiler is None:
            return

        self.profiler.disable()
        self.enabled = False

        if output_file:
            self.profiler.dump_stats(output_file)
            logger.info(f"性能分析结果已保存到: {output_file}")
        else:
            import pstats

            stats = pstats.Stats(self.profiler)
            stats.sort_stats("cumulative")
            logger.info("性能分析结果 (Top 20):")
            stats.print_stats(20)

    @contextmanager
    def profile(self, output_file: str | None = None):
        """性能分析上下文管理器"""
        self.start()
        try:
            yield
        finally:
            self.stop(output_file)
