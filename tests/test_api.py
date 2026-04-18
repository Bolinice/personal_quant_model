"""
API集成测试
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - register models
from app.db.base import Base, get_db
from app.main import app


# Use shared in-memory SQLite (static pool keeps same DB across connections)
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
Base.metadata.create_all(bind=_test_engine)


def _override_get_db():
    try:
        db = _TestSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


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
        response = client.get("/api/v1/market/stock-daily", params={
            "ts_code": "000001.SZ",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        })
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
