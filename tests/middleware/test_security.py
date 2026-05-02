"""
安全头中间件测试
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.security import SecurityHeadersMiddleware


@pytest.fixture
def app():
    """创建测试应用"""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "ok"}

    return app


@pytest.fixture
def client_with_security(app):
    """创建带安全头中间件的测试客户端"""
    app.add_middleware(SecurityHeadersMiddleware)
    return TestClient(app)


class TestSecurityHeadersBasic:
    """基础安全头测试"""

    def test_default_security_headers(self, client_with_security):
        """测试默认安全头"""
        response = client_with_security.get("/test")
        assert response.status_code == 200

        # CSP
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

        # X-Frame-Options
        assert response.headers["X-Frame-Options"] == "DENY"

        # X-Content-Type-Options
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        # X-XSS-Protection
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        # Referrer-Policy
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_hsts_not_added_for_http(self, client_with_security):
        """测试 HTTP 请求不添加 HSTS"""
        response = client_with_security.get("/test")
        assert "Strict-Transport-Security" not in response.headers


class TestSecurityHeadersConfiguration:
    """安全头配置测试"""

    def test_custom_csp_directives(self, app):
        """测试自定义 CSP 指令"""
        custom_csp = {
            "default-src": "'none'",
            "script-src": "'self' https://cdn.example.com",
            "style-src": "'self'",
        }
        app.add_middleware(SecurityHeadersMiddleware, csp_directives=custom_csp)
        client = TestClient(app)

        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "script-src 'self' https://cdn.example.com" in csp
        assert "style-src 'self'" in csp

    def test_disable_csp(self, app):
        """测试禁用 CSP"""
        app.add_middleware(SecurityHeadersMiddleware, enable_csp=False)
        client = TestClient(app)

        response = client.get("/test")
        assert "Content-Security-Policy" not in response.headers

    def test_custom_frame_options(self, app):
        """测试自定义 X-Frame-Options"""
        app.add_middleware(SecurityHeadersMiddleware, frame_options="SAMEORIGIN")
        client = TestClient(app)

        response = client.get("/test")
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_disable_frame_options(self, app):
        """测试禁用 X-Frame-Options"""
        app.add_middleware(SecurityHeadersMiddleware, enable_frame_options=False)
        client = TestClient(app)

        response = client.get("/test")
        assert "X-Frame-Options" not in response.headers

    def test_custom_referrer_policy(self, app):
        """测试自定义 Referrer-Policy"""
        app.add_middleware(SecurityHeadersMiddleware, referrer_policy="no-referrer")
        client = TestClient(app)

        response = client.get("/test")
        assert response.headers["Referrer-Policy"] == "no-referrer"

    def test_disable_all_optional_headers(self, app):
        """测试禁用所有可选头"""
        app.add_middleware(
            SecurityHeadersMiddleware,
            enable_hsts=False,
            enable_csp=False,
            enable_frame_options=False,
            enable_content_type_options=False,
            enable_xss_protection=False,
            enable_referrer_policy=False,
        )
        client = TestClient(app)

        response = client.get("/test")
        assert "Strict-Transport-Security" not in response.headers
        assert "Content-Security-Policy" not in response.headers
        assert "X-Frame-Options" not in response.headers
        assert "X-Content-Type-Options" not in response.headers
        assert "X-XSS-Protection" not in response.headers
        assert "Referrer-Policy" not in response.headers


class TestHSTS:
    """HSTS 测试"""

    def test_hsts_default_config(self, app):
        """测试 HSTS 默认配置"""
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app, base_url="https://testserver")

        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" not in hsts

    def test_hsts_with_preload(self, app):
        """测试 HSTS 预加载"""
        app.add_middleware(SecurityHeadersMiddleware, hsts_preload=True)
        client = TestClient(app, base_url="https://testserver")

        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "preload" in hsts

    def test_hsts_without_subdomains(self, app):
        """测试 HSTS 不包含子域名"""
        app.add_middleware(SecurityHeadersMiddleware, hsts_include_subdomains=False)
        client = TestClient(app, base_url="https://testserver")

        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "includeSubDomains" not in hsts

    def test_hsts_custom_max_age(self, app):
        """测试 HSTS 自定义最大年龄"""
        app.add_middleware(SecurityHeadersMiddleware, hsts_max_age=86400)  # 1 天
        client = TestClient(app, base_url="https://testserver")

        response = client.get("/test")
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=86400" in hsts


class TestCSP:
    """CSP 测试"""

    def test_csp_prevents_inline_scripts(self, app):
        """测试 CSP 防止内联脚本（概念测试）"""
        # 注意：实际的 CSP 执行由浏览器完成，这里只测试头部设置
        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_directives={
                "default-src": "'self'",
                "script-src": "'self'",  # 不允许 'unsafe-inline'
            },
        )
        client = TestClient(app)

        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]
        assert "script-src 'self'" in csp
        assert "'unsafe-inline'" not in csp

    def test_csp_allows_specific_domains(self, app):
        """测试 CSP 允许特定域名"""
        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_directives={
                "default-src": "'self'",
                "img-src": "'self' https://images.example.com",
                "connect-src": "'self' https://api.example.com",
            },
        )
        client = TestClient(app)

        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]
        assert "img-src 'self' https://images.example.com" in csp
        assert "connect-src 'self' https://api.example.com" in csp


class TestIntegration:
    """集成测试"""

    def test_multiple_requests_maintain_headers(self, client_with_security):
        """测试多次请求保持安全头"""
        for _ in range(3):
            response = client_with_security.get("/test")
            assert response.status_code == 200
            assert "Content-Security-Policy" in response.headers
            assert "X-Frame-Options" in response.headers

    def test_different_endpoints_same_headers(self, app):
        """测试不同端点使用相同安全头"""
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/endpoint1")
        async def endpoint1():
            return {"id": 1}

        @app.get("/endpoint2")
        async def endpoint2():
            return {"id": 2}

        client = TestClient(app)

        response1 = client.get("/endpoint1")
        response2 = client.get("/endpoint2")

        assert response1.headers["X-Frame-Options"] == response2.headers["X-Frame-Options"]
        assert response1.headers["Content-Security-Policy"] == response2.headers["Content-Security-Policy"]
