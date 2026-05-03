"""
慢查询监控中间件

功能：
1. 记录所有SQL查询的执行时间
2. 检测慢查询（超过阈值）
3. 检测N+1查询模式
4. 生成查询性能报告
"""

import time
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from contextlib import contextmanager
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class QueryMonitor:
    """查询监控器"""

    def __init__(self, slow_query_threshold: float = 0.1):
        """
        Args:
            slow_query_threshold: 慢查询阈值（秒），默认100ms
        """
        self.slow_query_threshold = slow_query_threshold
        self.query_stats: Dict[str, List[float]] = defaultdict(list)
        self.slow_queries: List[Dict] = []
        self.n_plus_one_warnings: List[Dict] = []
        self._enabled = True

    def record_query(self, statement: str, duration: float, context: Optional[str] = None):
        """记录查询"""
        if not self._enabled:
            return

        # 标准化SQL语句（移除参数值）
        normalized = self._normalize_sql(statement)
        self.query_stats[normalized].append(duration)

        # 检测慢查询
        if duration > self.slow_query_threshold:
            self.slow_queries.append({
                "statement": statement,
                "duration": duration,
                "context": context,
                "timestamp": time.time()
            })
            logger.warning(
                f"Slow query detected ({duration:.3f}s): {statement[:200]}",
                extra={"duration": duration, "context": context}
            )

    def detect_n_plus_one(self, session: Session):
        """检测N+1查询模式"""
        if not self._enabled:
            return

        # 分析查询模式：如果同一个查询在短时间内执行多次，可能是N+1
        for sql, durations in self.query_stats.items():
            if len(durations) > 10:  # 同一查询执行超过10次
                total_time = sum(durations)
                avg_time = total_time / len(durations)

                if total_time > self.slow_query_threshold:
                    self.n_plus_one_warnings.append({
                        "statement": sql,
                        "count": len(durations),
                        "total_time": total_time,
                        "avg_time": avg_time,
                        "timestamp": time.time()
                    })
                    logger.warning(
                        f"Potential N+1 query detected: {sql[:200]} "
                        f"(executed {len(durations)} times, total {total_time:.3f}s)"
                    )

    def get_report(self) -> Dict:
        """生成查询性能报告"""
        total_queries = sum(len(durations) for durations in self.query_stats.values())
        total_time = sum(sum(durations) for durations in self.query_stats.values())

        # 找出最慢的查询
        slowest_queries = sorted(
            [
                {
                    "statement": sql,
                    "max_duration": max(durations),
                    "avg_duration": sum(durations) / len(durations),
                    "count": len(durations),
                    "total_time": sum(durations)
                }
                for sql, durations in self.query_stats.items()
            ],
            key=lambda x: x["total_time"],
            reverse=True
        )[:10]

        return {
            "total_queries": total_queries,
            "total_time": total_time,
            "slow_queries_count": len(self.slow_queries),
            "n_plus_one_warnings_count": len(self.n_plus_one_warnings),
            "slowest_queries": slowest_queries,
            "slow_queries": self.slow_queries[-10:],  # 最近10个慢查询
            "n_plus_one_warnings": self.n_plus_one_warnings[-10:]  # 最近10个N+1警告
        }

    def reset(self):
        """重置统计数据"""
        self.query_stats.clear()
        self.slow_queries.clear()
        self.n_plus_one_warnings.clear()

    def enable(self):
        """启用监控"""
        self._enabled = True

    def disable(self):
        """禁用监控"""
        self._enabled = False

    @staticmethod
    def _normalize_sql(statement: str) -> str:
        """标准化SQL语句，移除参数值"""
        # 简单实现：移除数字和字符串字面量
        import re
        normalized = re.sub(r"'[^']*'", "'?'", statement)
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        return normalized


# 全局监控器实例
_global_monitor: Optional[QueryMonitor] = None


def get_query_monitor() -> QueryMonitor:
    """获取全局查询监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = QueryMonitor()
    return _global_monitor


def setup_query_monitoring(engine: Engine, slow_query_threshold: float = 0.1):
    """
    设置查询监控

    Args:
        engine: SQLAlchemy引擎
        slow_query_threshold: 慢查询阈值（秒）
    """
    global _global_monitor
    _global_monitor = QueryMonitor(slow_query_threshold=slow_query_threshold)

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault('query_start_time', []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get('query_start_time', [])
        if start_times:
            start_time = start_times.pop()
            duration = time.time() - start_time
            _global_monitor.record_query(statement, duration)

    logger.info(f"Query monitoring enabled (threshold: {slow_query_threshold}s)")


@contextmanager
def monitor_queries(context: str = ""):
    """
    查询监控上下文管理器

    用法:
        with monitor_queries("model_scoring"):
            # 执行数据库操作
            ...
    """
    monitor = get_query_monitor()
    monitor.reset()

    start_time = time.time()
    try:
        yield monitor
    finally:
        duration = time.time() - start_time
        report = monitor.get_report()

        if report["slow_queries_count"] > 0 or report["n_plus_one_warnings_count"] > 0:
            logger.warning(
                f"Query monitoring report for '{context}': "
                f"{report['total_queries']} queries in {duration:.3f}s, "
                f"{report['slow_queries_count']} slow queries, "
                f"{report['n_plus_one_warnings_count']} N+1 warnings"
            )
