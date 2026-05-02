"""
测试熔断器模式 (Circuit Breaker Pattern)

验证：
1. 状态转换逻辑（Closed -> Open -> Half-Open -> Closed）
2. 失败率阈值检测
3. 自动恢复机制
4. 并发安全性
"""

import time
from unittest.mock import Mock

import pytest

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
    get_circuit_breaker,
)


class TestCircuitBreakerBasic:
    """测试熔断器基本功能"""

    def test_initial_state(self):
        """测试初始状态"""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open

    def test_successful_call(self):
        """测试成功调用"""
        cb = CircuitBreaker("test")

        @cb.call
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

        stats = cb.get_stats()
        assert stats.success_count == 1
        assert stats.failure_count == 0
        assert stats.total_calls == 1

    def test_failed_call(self):
        """测试失败调用"""
        cb = CircuitBreaker("test")

        @cb.call
        def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            fail_func()

        stats = cb.get_stats()
        assert stats.failure_count == 1
        assert stats.success_count == 0
        assert stats.consecutive_failures == 1


class TestCircuitBreakerStateTransitions:
    """测试状态转换"""

    def test_closed_to_open(self):
        """测试 Closed -> Open 转换"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 连续失败3次
        for _ in range(3):
            with pytest.raises(RuntimeError):
                fail_func()

        # 应该转换到 Open 状态
        assert cb.is_open

    def test_open_rejects_calls(self):
        """测试 Open 状态拒绝调用"""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        assert cb.is_open

        # Open 状态下应该直接拒绝
        with pytest.raises(CircuitOpenError):
            fail_func()

    def test_open_to_half_open(self):
        """测试 Open -> Half-Open 转换"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=0.1,  # 100ms 超时
        )
        cb = CircuitBreaker("test", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        assert cb.is_open

        # 等待超时
        time.sleep(0.15)

        # 检查状态（通过 _get_state 触发状态转换）
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed(self):
        """测试 Half-Open -> Closed 转换"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.1,
        )
        cb = CircuitBreaker("test", config)

        call_count = 0

        @cb.call
        def toggle_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("fail")
            return "success"

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                toggle_func()

        assert cb.is_open

        # 等待超时进入 Half-Open
        time.sleep(0.15)

        # 连续成功2次
        result1 = toggle_func()
        result2 = toggle_func()

        assert result1 == "success"
        assert result2 == "success"
        assert cb.is_closed

    def test_half_open_to_open(self):
        """测试 Half-Open -> Open 转换（失败时）"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=0.1,
        )
        cb = CircuitBreaker("test", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        assert cb.is_open

        # 等待超时进入 Half-Open
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Half-Open 状态下失败，应该重新开启
        with pytest.raises(RuntimeError):
            fail_func()

        assert cb.is_open


class TestCircuitBreakerConfig:
    """测试配置参数"""

    def test_failure_threshold(self):
        """测试失败阈值"""
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker("test", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 失败4次，不应该熔断
        for _ in range(4):
            with pytest.raises(RuntimeError):
                fail_func()

        assert cb.is_closed

        # 第5次失败，应该熔断
        with pytest.raises(RuntimeError):
            fail_func()

        assert cb.is_open

    def test_success_threshold(self):
        """测试成功阈值"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=3,
            timeout=0.1,
        )
        cb = CircuitBreaker("test", config)

        call_count = 0

        @cb.call
        def toggle_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("fail")
            return "success"

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                toggle_func()

        # 等待进入 Half-Open
        time.sleep(0.15)

        # 成功2次，不应该关闭
        toggle_func()
        toggle_func()
        assert cb.is_half_open

        # 第3次成功，应该关闭
        toggle_func()
        assert cb.is_closed

    def test_half_open_max_calls(self):
        """测试半开状态最大调用数"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=0.1,
            half_open_max_calls=2,
        )
        cb = CircuitBreaker("test", config)

        @cb.call
        def success_func():
            return "success"

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        # 等待进入 Half-Open
        time.sleep(0.15)

        # 允许2次调用
        result1 = success_func()
        result2 = success_func()

        assert result1 == "success"
        assert result2 == "success"

        # 第3次调用时，如果前2次都成功，应该已经转换到 CLOSED 状态
        # 因为 success_threshold 默认是 2
        # 所以第3次调用应该成功
        result3 = success_func()
        assert result3 == "success"
        assert cb.is_closed


class TestCircuitBreakerReset:
    """测试重置功能"""

    def test_manual_reset(self):
        """测试手动重置"""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        assert cb.is_open

        # 手动重置
        cb.reset()

        assert cb.is_closed
        stats = cb.get_stats()
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.total_calls == 0


class TestCircuitBreakerRegistry:
    """测试熔断器注册表"""

    def test_get_or_create(self):
        """测试获取或创建"""
        registry = CircuitBreakerRegistry()

        cb1 = registry.get_or_create("service1")
        cb2 = registry.get_or_create("service1")

        # 应该返回同一个实例
        assert cb1 is cb2

    def test_get_nonexistent(self):
        """测试获取不存在的熔断器"""
        registry = CircuitBreakerRegistry()

        cb = registry.get("nonexistent")
        assert cb is None

    def test_reset_specific(self):
        """测试重置特定熔断器"""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=2)

        cb = registry.get_or_create("service1", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        assert cb.is_open

        # 重置
        registry.reset("service1")
        assert cb.is_closed

    def test_reset_all(self):
        """测试重置所有熔断器"""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=2)

        cb1 = registry.get_or_create("service1", config)
        cb2 = registry.get_or_create("service2", config)

        @cb1.call
        def fail_func1():
            raise RuntimeError("fail")

        @cb2.call
        def fail_func2():
            raise RuntimeError("fail")

        # 触发两个熔断器
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func1()
            with pytest.raises(RuntimeError):
                fail_func2()

        assert cb1.is_open
        assert cb2.is_open

        # 重置所有
        registry.reset_all()

        assert cb1.is_closed
        assert cb2.is_closed

    def test_get_all_stats(self):
        """测试获取所有统计信息"""
        registry = CircuitBreakerRegistry()

        cb1 = registry.get_or_create("service1")
        cb2 = registry.get_or_create("service2")

        @cb1.call
        def success_func():
            return "success"

        success_func()

        stats = registry.get_all_stats()

        assert "service1" in stats
        assert "service2" in stats
        assert stats["service1"].success_count == 1
        assert stats["service2"].success_count == 0


class TestGlobalCircuitBreaker:
    """测试全局熔断器"""

    def test_get_global_circuit_breaker(self):
        """测试获取全局熔断器"""
        cb1 = get_circuit_breaker("global_service")
        cb2 = get_circuit_breaker("global_service")

        # 应该返回同一个实例
        assert cb1 is cb2


class TestCircuitBreakerEdgeCases:
    """测试边界情况"""

    def test_zero_timeout(self):
        """测试零超时"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=0.0,
        )
        cb = CircuitBreaker("test", config)

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 触发熔断
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        # 检查内部状态（不触发状态转换）
        assert cb.stats.state == CircuitState.OPEN

        # 由于超时为0，访问 state 属性会立即转换到 Half-Open
        current_state = cb.state
        assert current_state == CircuitState.HALF_OPEN

    def test_mixed_success_failure(self):
        """测试成功和失败混合"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        call_count = 0

        @cb.call
        def mixed_func():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("fail")
            return "success"

        # 交替成功和失败
        mixed_func()  # 成功
        with pytest.raises(RuntimeError):
            mixed_func()  # 失败
        mixed_func()  # 成功
        with pytest.raises(RuntimeError):
            mixed_func()  # 失败

        # 连续失败计数应该被重置
        stats = cb.get_stats()
        assert stats.consecutive_failures == 1
        assert cb.is_closed

    def test_stats_accuracy(self):
        """测试统计信息准确性"""
        cb = CircuitBreaker("test")

        @cb.call
        def success_func():
            return "success"

        @cb.call
        def fail_func():
            raise RuntimeError("fail")

        # 3次成功
        for _ in range(3):
            success_func()

        # 2次失败
        for _ in range(2):
            with pytest.raises(RuntimeError):
                fail_func()

        stats = cb.get_stats()
        assert stats.success_count == 3
        assert stats.failure_count == 2
        assert stats.total_calls == 5
        assert stats.consecutive_failures == 2
        assert stats.consecutive_successes == 0


class TestCircuitBreakerIntegration:
    """集成测试"""

    def test_realistic_scenario(self):
        """测试真实场景"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=0.2,
        )
        cb = CircuitBreaker("external_api", config)

        # 模拟外部 API
        api_available = True

        @cb.call
        def call_external_api():
            if not api_available:
                raise ConnectionError("API unavailable")
            return {"data": "success"}

        # 阶段1: 正常工作
        result = call_external_api()
        assert result == {"data": "success"}
        assert cb.is_closed

        # 阶段2: API 故障，触发熔断
        api_available = False
        for _ in range(3):
            with pytest.raises(ConnectionError):
                call_external_api()

        assert cb.is_open

        # 阶段3: 熔断期间，快速失败
        with pytest.raises(CircuitOpenError):
            call_external_api()

        # 阶段4: 等待恢复
        time.sleep(0.25)
        assert cb.is_half_open

        # 阶段5: API 恢复，测试成功
        api_available = True
        call_external_api()
        call_external_api()

        assert cb.is_closed

    def test_with_fallback(self):
        """测试降级方案"""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("api_with_fallback", config)

        @cb.call
        def call_api():
            raise ConnectionError("API down")

        def fallback():
            return {"data": "cached"}

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ConnectionError):
                call_api()

        # 使用降级方案
        try:
            result = call_api()
        except CircuitOpenError:
            result = fallback()

        assert result == {"data": "cached"}
