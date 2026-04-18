"""
API集成测试
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


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
        assert response.status_code == 401


class TestMarketAPI:
    """市场数据API测试"""

    def test_get_market_data(self, client):
        # Market API requires ts_code, start_date, end_date params
        response = client.get("/api/v1/market/stock-daily", params={
            "ts_code": "000001.SZ",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        })
        # With empty test DB, expect 404 (no data) not 422 (validation error)
        assert response.status_code in [200, 404]


class TestFactorAPI:
    """因子API测试"""

    def test_list_factors(self, client):
        response = client.get("/api/v1/factors/")
        assert response.status_code == 200


class TestBacktestAPI:
    """回测API测试"""

    def test_list_backtests(self, client):
        response = client.get("/api/v1/backtests/")
        assert response.status_code == 200


class TestStrategyAPI:
    """策略API测试"""

    def test_list_strategies(self, client):
        response = client.get("/api/v1/strategies/")
        assert response.status_code == 200


class TestNotificationAPI:
    """通知API测试"""

    def test_list_notifications(self, client):
        response = client.get("/api/v1/notifications/")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
