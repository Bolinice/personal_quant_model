"""
API集成测试 - 使用conftest.py中的共享fixtures
"""
import pytest


class TestHealthCheck:
    """健康检查测试"""

    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200


class TestAuthAPI:
    """认证API测试"""

    def test_login_missing_credentials(self, client):
        response = client.post("/api/v1/auth/login", data={
            "username": "nonexistent",
            "password": "wrong",
        })
        assert response.status_code in [401, 422, 400]


class TestMarketAPI:
    """市场数据API测试"""

    def test_get_market_data(self, client):
        response = client.get("/api/v1/market/stock-daily", params={
            "ts_code": "000001.SZ",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        })
        assert response.status_code in [200, 404]


class TestFactorAPI:
    """因子API测试 - 需要认证"""

    def test_list_factors_requires_auth(self, client):
        """因子列表端点需要认证"""
        response = client.get("/api/v1/factors/")
        assert response.status_code == 401

    def test_list_factors_with_auth(self, client, auth_headers):
        """带认证的因子列表端点应返回200"""
        response = client.get("/api/v1/factors/", headers=auth_headers)
        assert response.status_code == 200


class TestBacktestAPI:
    """回测API测试 - 需要认证"""

    def test_list_backtests_requires_auth(self, client):
        """回测列表端点需要认证"""
        response = client.get("/api/v1/backtests/")
        assert response.status_code == 401

    def test_list_backtests_with_auth(self, client, auth_headers):
        """带认证的回测列表端点应返回200"""
        response = client.get("/api/v1/backtests/", headers=auth_headers)
        assert response.status_code == 200


class TestStrategyAPI:
    """策略API测试 - 需要认证"""

    def test_list_strategies_requires_auth(self, client):
        """策略列表端点需要认证"""
        response = client.get("/api/v1/strategies/")
        assert response.status_code == 401

    def test_list_strategies_with_auth(self, client, auth_headers):
        """带认证的策略列表端点应返回200"""
        response = client.get("/api/v1/strategies/", headers=auth_headers)
        assert response.status_code == 200


class TestNotificationAPI:
    """通知API测试"""

    def test_list_notifications(self, client):
        response = client.get("/api/v1/notifications/")
        assert response.status_code == 200


class TestProductsAPI:
    """产品API测试"""

    def test_list_products(self, client):
        response = client.get("/api/v1/products/")
        assert response.status_code == 200


class TestContentAPI:
    """内容管理API测试"""

    def test_get_content(self, client):
        response = client.get("/api/v1/content/")
        assert response.status_code in [200, 404]


class TestUsageAPI:
    """用量统计API测试"""

    def test_get_usage(self, client):
        response = client.get("/api/v1/usage/")
        assert response.status_code in [200, 401, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
