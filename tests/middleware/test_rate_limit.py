"""
速率限制中间件测试
"""

import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    RateLimitMiddleware,
)


@pytest.fixture
def app():
    """创建测试应用"""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "ok"}

    @app.get("/exempt")
    async def exempt_endpoint():
        return {"message": "exempt"}

    return app


@pytest.fixture
def limiter():
    """创建内存限流器"""
    return InMemoryRateLimiter()


class TestInMemoryRateLimiter:
    """内存速率限制器测试"""

    def test_allows_requests_within_limit(self, limiter):
        """测试限制内的请求被允许"""
        for i in range(5):
            allowed, _ = limiter.is_allowed("test_key", limit=5, window=60)
            assert allowed, f"Request {i+1} should be allowed"

    def test_blocks_requests_exceeding_limit(self, limiter):
        """测试超出限制的请求被阻止"""
        # 发送 5 个请求（限制为 5）
        for _ in range(5):
            allowed, _ = limiter.is_allowed("test_key", limit=5, window=60)
            assert allowed

        # 第 6 个请求应该被阻止
        allowed, retry_after = limiter.is_allowed("test_key", limit=5, window=60)
        assert not allowed
        assert retry_after > 0

    def test_sliding_window_expiration(self, limiter):
        """测试滑动窗口过期"""
        # 发送 3 个请求
        for _ in range(3):
            limiter.is_allowed("test_key", limit=3, window=1)

        # 等待窗口过期
        time.sleep(1.1)

        # 应该可以再次发送请求
        allowed, _ = limiter.is_allowed("test_key", limit=3, window=1)
        assert allowed

    def test_different_keys_independent(self, limiter):
        """测试不同键独立限流"""
        # key1 达到限制
        for _ in range(5):
            limiter.is_allowed("key1", limit=5, window=60)

        # key2 应该不受影响
        allowed, _ = limiter.is_allowed("key2", limit=5, window=60)
        assert allowed

    def test_reset_key(self, limiter):
        """测试重置键"""
        # 达到限制
        for _ in range(5):
            limiter.is_allowed("test_key", limit=5, window=60)

        # 重置
        limiter.reset("test_key")

        # 应该可以再次发送请求
        allowed, _ = limiter.is_allowed("test_key", limit=5, window=60)
        assert allowed

    def test_clear_all(self, limiter):
        """测试清空所有记录"""
        # 多个键达到限制
        for _ in range(3):
            limiter.is_allowed("key1", limit=3, window=60)
            limiter.is_allowed("key2", limit=3, window=60)

        # 清空
        limiter.clear()

        # 所有键应该可以再次发送请求
        allowed1, _ = limiter.is_allowed("key1", limit=3, window=60)
        allowed2, _ = limiter.is_allowed("key2", limit=3, window=60)
        assert allowed1
        assert allowed2

    def test_retry_after_calculation(self, limiter):
        """测试重试等待时间计算"""
        # 发送请求直到达到限制
        for _ in range(5):
            limiter.is_allowed("test_key", limit=5, window=10)

        # 检查重试等待时间
        allowed, retry_after = limiter.is_allowed("test_key", limit=5, window=10)
        assert not allowed
        assert 0 < retry_after <= 11  # 应该在 1-11 秒之间


class TestRateLimitMiddleware:
    """速率限制中间件测试"""

    def test_allows_requests_within_limit(self, app, limiter):
        """测试限制内的请求被允许"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=5, default_window=60)
        client = TestClient(app)

        for i in range(5):
            response = client.get("/test")
            assert response.status_code == 200, f"Request {i+1} should succeed"

    def test_blocks_requests_exceeding_limit(self, app, limiter):
        """测试超出限制的请求被阻止"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=3, default_window=60)
        client = TestClient(app)

        # 前 3 个请求成功
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

        # 第 4 个请求被阻止
        response = client.get("/test")
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_rate_limit_headers(self, app, limiter):
        """测试速率限制响应头"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=10, default_window=60)
        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "10"
        assert response.headers["X-RateLimit-Window"] == "60"

    def test_exempt_paths(self, app, limiter):
        """测试豁免路径"""
        app.add_middleware(
            RateLimitMiddleware,
            limiter=limiter,
            default_limit=2,
            default_window=60,
            exempt_paths=["/exempt"],
        )
        client = TestClient(app)

        # /test 路径受限
        for _ in range(2):
            response = client.get("/test")
            assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429

        # /exempt 路径不受限
        for _ in range(5):
            response = client.get("/exempt")
            assert response.status_code == 200

    def test_custom_key_function(self, app, limiter):
        """测试自定义键生成函数"""

        def custom_key_func(request: Request) -> str:
            # 使用 User-Agent 作为键
            return f"ua:{request.headers.get('user-agent', 'unknown')}"

        app.add_middleware(
            RateLimitMiddleware,
            limiter=limiter,
            default_limit=3,
            default_window=60,
            key_func=custom_key_func,
        )
        client = TestClient(app)

        # 使用不同的 User-Agent
        for _ in range(3):
            response = client.get("/test", headers={"User-Agent": "Browser1"})
            assert response.status_code == 200

        # Browser1 达到限制
        response = client.get("/test", headers={"User-Agent": "Browser1"})
        assert response.status_code == 429

        # Browser2 不受影响
        response = client.get("/test", headers={"User-Agent": "Browser2"})
        assert response.status_code == 200

    def test_retry_after_header(self, app, limiter):
        """测试 Retry-After 响应头"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=2, default_window=10)
        client = TestClient(app)

        # 达到限制
        for _ in range(2):
            client.get("/test")

        # 检查 Retry-After 头
        response = client.get("/test")
        assert response.status_code == 429
        retry_after = int(response.headers["Retry-After"])
        assert 0 < retry_after <= 11


class TestRateLimitExceeded:
    """速率限制异常测试"""

    def test_exception_status_code(self):
        """测试异常状态码"""
        exc = RateLimitExceeded(retry_after=60)
        assert exc.status_code == 429

    def test_exception_detail(self):
        """测试异常详情"""
        exc = RateLimitExceeded(retry_after=60)
        assert "Rate limit exceeded" in exc.detail

    def test_exception_headers(self):
        """测试异常响应头"""
        exc = RateLimitExceeded(retry_after=120)
        assert exc.headers["Retry-After"] == "120"


class TestEdgeCases:
    """边界情况测试"""

    def test_zero_limit(self, app, limiter):
        """测试零限制（所有请求被阻止）"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=0, default_window=60)
        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 429

    def test_very_short_window(self, limiter):
        """测试极短时间窗口"""
        # 发送请求
        allowed, _ = limiter.is_allowed("test_key", limit=2, window=1)
        assert allowed

        # 等待窗口过期
        time.sleep(1.1)

        # 应该可以再次发送请求
        allowed, _ = limiter.is_allowed("test_key", limit=2, window=1)
        assert allowed

    def test_concurrent_requests_same_key(self, app, limiter):
        """测试同一键的并发请求"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=5, default_window=60)
        client = TestClient(app)

        # 模拟并发请求（TestClient 是同步的，这里顺序执行）
        responses = [client.get("/test") for _ in range(7)]

        success_count = sum(1 for r in responses if r.status_code == 200)
        blocked_count = sum(1 for r in responses if r.status_code == 429)

        assert success_count == 5
        assert blocked_count == 2

    def test_no_client_ip(self, app, limiter):
        """测试无客户端 IP 的情况"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=3, default_window=60)

        # 创建没有客户端信息的请求
        @app.get("/no-client")
        async def no_client_endpoint(request: Request):
            # 模拟无客户端 IP
            request.scope["client"] = None
            return {"message": "ok"}

        client = TestClient(app)

        # 应该使用 "unknown" 作为键
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200


class TestIntegration:
    """集成测试"""

    def test_rate_limit_resets_after_window(self, app, limiter):
        """测试时间窗口后限流重置"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=2, default_window=1)
        client = TestClient(app)

        # 达到限制
        for _ in range(2):
            response = client.get("/test")
            assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429

        # 等待窗口过期
        time.sleep(1.1)

        # 应该可以再次发送请求
        response = client.get("/test")
        assert response.status_code == 200

    def test_multiple_endpoints_share_limit(self, app, limiter):
        """测试多个端点共享限流"""
        app.add_middleware(RateLimitMiddleware, limiter=limiter, default_limit=3, default_window=60)

        @app.get("/endpoint1")
        async def endpoint1():
            return {"id": 1}

        @app.get("/endpoint2")
        async def endpoint2():
            return {"id": 2}

        client = TestClient(app)

        # 混合请求不同端点
        client.get("/endpoint1")
        client.get("/endpoint2")
        client.get("/endpoint1")

        # 第 4 个请求应该被阻止（无论哪个端点）
        response = client.get("/endpoint2")
        assert response.status_code == 429
