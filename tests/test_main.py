import pytest
from fastapi.testclient import TestClient

def test_root_endpoint(client):
    """测试根端点"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "A股多因子增强策略平台 API"
    assert "version" in response.json()

def test_health_check(client):
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    assert status in response.json()
    assert response.json()["status"] == "healthy"