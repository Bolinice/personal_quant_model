"""
熔断器测试
"""

import time

import pytest

from app.data_sources.base import CircuitBreaker, CircuitBreakerOpenError


class TestCircuitBreaker:
    """熔断器状态机测试"""

    def test_closed_state_normal_call(self):
        """CLOSED 状态下正常调用"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == "CLOSED"

    def test_open_after_threshold_failures(self):
        """连续失败达到阈值后进入 OPEN 状态"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        for _i in range(3):
            with pytest.raises(ValueError, match="fail"):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == "OPEN"
        assert cb._failure_count == 3

    def test_open_state_rejects_calls(self):
        """OPEN 状态下拒绝调用"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        with pytest.raises(ValueError, match="fail"):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == "OPEN"
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: 42)

    def test_half_open_after_recovery_timeout(self):
        """恢复超时后进入 HALF_OPEN 状态"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        with pytest.raises(ValueError, match="fail"):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == "OPEN"
        time.sleep(0.2)  # 等待恢复超时

        # HALF_OPEN 状态下允许一次试探调用
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == "CLOSED"

    def test_half_open_failure_reopens(self):
        """HALF_OPEN 状态下失败重新进入 OPEN"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        with pytest.raises(ValueError, match="fail"):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        time.sleep(0.2)

        # HALF_OPEN 试探失败
        with pytest.raises(ValueError, match="fail"):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == "OPEN"

    def test_success_resets_failure_count(self):
        """成功调用重置失败计数"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        with pytest.raises(ValueError, match="fail"):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb._failure_count == 1

        # 成功调用重置计数
        cb.call(lambda: 42)
        assert cb._failure_count == 0
        assert cb.state == "CLOSED"
