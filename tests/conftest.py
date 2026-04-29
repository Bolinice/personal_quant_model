import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.db.base import Base, get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import AuthService

# ==================== Golden Master CLI Option ====================


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", default=False, help="Update golden master files")


@pytest.fixture
def update_golden(request):
    """判断是否更新 golden master"""
    return request.config.getoption("update_golden")


# Use shared in-memory SQLite for tests (StaticPool keeps same DB across connections)
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_headers(client, db):
    """创建测试用户并返回认证头"""
    # 创建测试用户（如果不存在）
    existing = db.query(User).filter(User.username == "testuser").first()
    if not existing:
        user = AuthService.create_user(
            db,
            "testuser",
            "test@example.com",
            "TestPass1",
            role="admin",
        )
    else:
        user = existing

    # 生成 access token
    token_data = {"sub": user.username, "role": user.role, "type": "access"}
    access_token = AuthService.create_access_token(token_data)
    return {"Authorization": f"Bearer {access_token}"}
