"""
熔断器模式 (Circuit Breaker Pattern)

保护系统免受级联故障影响，当外部服务频繁失败时自动切断请求，避免资源耗尽。

核心概念：
- Closed（闭合）: 正常状态，请求正常通过
- Open（开启）: 熔断状态，直接拒绝请求，快速失败
- Half-Open（半开）: 恢复测试状态，允许少量请求通过以测试服务是否恢复

状态转换：
    Closed --[失败率超过阈值]--> Open
    Open --[超时后]--> Half-Open
    Half-Open --[测试成功]--> Closed
    Half-Open --[测试失败]--> Open

参考：
- Netflix Hystrix
- Martin Fowler's Circuit Breaker Pattern
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 闭合：正常工作
    OPEN = "open"  # 开启：熔断中，拒绝请求
    HALF_OPEN = "half_open"  # 半开：测试恢复


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    failure_threshold: int = 5  # 失败次数阈值
    success_threshold: int = 2  # 半开状态下成功次数阈值
    timeout: float = 60.0  # 熔断超时时间（秒）
    window_size: int = 10  # 滑动窗口大小
    half_open_max_calls: int = 3  # 半开状态下最大允许请求数


@dataclass
class CircuitBreakerStats:
    """熔断器统计信息"""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    last_failure_time: datetime | None = None
    last_state_change: datetime = field(default_factory=datetime.now)
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreakerError(Exception):
    """熔断器异常"""

    pass


class CircuitOpenError(CircuitBreakerError):
    """熔断器开启异常（服务不可用）"""

    def __init__(self, message: str = "Circuit breaker is OPEN"):
        self.message = message
        super().__init__(self.message)


class CircuitBreaker:
    """
    熔断器

    Example:
        >>> cb = CircuitBreaker(name="api_service")
        >>>
        >>> @cb.call
        ... def fetch_data():
        ...     # 可能失败的外部调用
        ...     return requests.get("https://api.example.com/data")
        >>>
        >>> try:
        ...     data = fetch_data()
        ... except CircuitOpenError:
        ...     # 熔断器开启，使用降级方案
        ...     data = get_cached_data()
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """
        Args:
            name: 熔断器名称（用于日志和监控）
            config: 熔断器配置
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = Lock()
        self._failure_window: deque[float] = deque(maxlen=self.config.window_size)
        self._half_open_calls = 0

    def call(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        装饰器：包装函数调用，添加熔断保护

        Args:
            func: 要保护的函数

        Returns:
            包装后的函数
        """

        def wrapper(*args: Any, **kwargs: Any) -> T:
            return self._execute(func, *args, **kwargs)

        return wrapper

    def _execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        执行函数调用，应用熔断逻辑

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            CircuitOpenError: 熔断器开启时
            Exception: 函数执行失败时
        """
        with self._lock:
            self.stats.total_calls += 1

            # 检查状态
            current_state = self._get_state()

            if current_state == CircuitState.OPEN:
                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Last failure: {self.stats.last_failure_time}"
                )

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN and max calls reached"
                    )
                self._half_open_calls += 1

        # 执行函数（在锁外执行，避免阻塞）
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _get_state(self) -> CircuitState:
        """
        获取当前状态（考虑超时自动恢复）

        Returns:
            当前熔断器状态
        """
        if self.stats.state == CircuitState.OPEN:
            # 检查是否超时，可以尝试恢复
            if self.stats.last_failure_time:
                elapsed = (datetime.now() - self.stats.last_failure_time).total_seconds()
                if elapsed >= self.config.timeout:
                    self._transition_to(CircuitState.HALF_OPEN)

        return self.stats.state

    def _on_success(self) -> None:
        """处理成功调用"""
        with self._lock:
            self.stats.success_count += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0

            if self.stats.state == CircuitState.HALF_OPEN:
                # 半开状态下，连续成功达到阈值则关闭熔断器
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    self._reset_counts()

    def _on_failure(self) -> None:
        """处理失败调用"""
        with self._lock:
            self.stats.failure_count += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = datetime.now()

            # 记录失败时间到滑动窗口
            self._failure_window.append(time.time())

            if self.stats.state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即重新开启熔断器
                self._transition_to(CircuitState.OPEN)
            elif self.stats.state == CircuitState.CLOSED:
                # 闭合状态下，检查失败率
                if self._should_open():
                    self._transition_to(CircuitState.OPEN)

    def _should_open(self) -> bool:
        """
        判断是否应该开启熔断器

        Returns:
            是否应该开启
        """
        # 方法1: 连续失败次数
        if self.stats.consecutive_failures >= self.config.failure_threshold:
            return True

        # 方法2: 滑动窗口内失败率
        if len(self._failure_window) >= self.config.window_size:
            # 窗口已满，检查失败率
            window_duration = self._failure_window[-1] - self._failure_window[0]
            if window_duration < self.config.timeout:
                # 在短时间内失败次数过多
                return True

        return False

    def _transition_to(self, new_state: CircuitState) -> None:
        """
        状态转换

        Args:
            new_state: 新状态
        """
        old_state = self.stats.state
        self.stats.state = new_state
        self.stats.last_state_change = datetime.now()

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        # 日志记录状态转换
        # logger.info(f"Circuit breaker '{self.name}' transitioned from {old_state.value} to {new_state.value}")

    def _reset_counts(self) -> None:
        """重置计数器"""
        self.stats.consecutive_failures = 0
        self.stats.consecutive_successes = 0
        self._failure_window.clear()
        self._half_open_calls = 0

    def reset(self) -> None:
        """手动重置熔断器到闭合状态"""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._reset_counts()
            self.stats.failure_count = 0
            self.stats.success_count = 0
            self.stats.total_calls = 0
            self.stats.last_failure_time = None

    def get_stats(self) -> CircuitBreakerStats:
        """
        获取统计信息

        Returns:
            熔断器统计信息
        """
        with self._lock:
            return CircuitBreakerStats(
                state=self.stats.state,
                failure_count=self.stats.failure_count,
                success_count=self.stats.success_count,
                total_calls=self.stats.total_calls,
                last_failure_time=self.stats.last_failure_time,
                last_state_change=self.stats.last_state_change,
                consecutive_failures=self.stats.consecutive_failures,
                consecutive_successes=self.stats.consecutive_successes,
            )

    @property
    def state(self) -> CircuitState:
        """当前状态"""
        with self._lock:
            return self._get_state()

    @property
    def is_closed(self) -> bool:
        """是否闭合"""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """是否开启"""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """是否半开"""
        return self.state == CircuitState.HALF_OPEN


class CircuitBreakerRegistry:
    """
    熔断器注册表

    管理多个熔断器实例，提供全局访问点。

    Example:
        >>> registry = CircuitBreakerRegistry()
        >>> cb = registry.get_or_create("tushare_api")
        >>>
        >>> @cb.call
        ... def fetch_stock_data():
        ...     return tushare.pro_bar(ts_code="000001.SZ")
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = Lock()

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """
        获取或创建熔断器

        Args:
            name: 熔断器名称
            config: 熔断器配置（仅在创建时使用）

        Returns:
            熔断器实例
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """
        获取熔断器

        Args:
            name: 熔断器名称

        Returns:
            熔断器实例，不存在则返回 None
        """
        with self._lock:
            return self._breakers.get(name)

    def reset(self, name: str) -> None:
        """
        重置指定熔断器

        Args:
            name: 熔断器名称
        """
        with self._lock:
            if name in self._breakers:
                self._breakers[name].reset()

    def reset_all(self) -> None:
        """重置所有熔断器"""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def get_all_stats(self) -> dict[str, CircuitBreakerStats]:
        """
        获取所有熔断器的统计信息

        Returns:
            熔断器名称到统计信息的映射
        """
        with self._lock:
            return {name: breaker.get_stats() for name, breaker in self._breakers.items()}


# 全局熔断器注册表
_global_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """
    获取全局熔断器实例

    Args:
        name: 熔断器名称
        config: 熔断器配置（仅在首次创建时使用）

    Returns:
        熔断器实例
    """
    return _global_registry.get_or_create(name, config)
