from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """应用配置 - 所有敏感值必须从环境变量读取"""

    # 数据库 - PostgreSQL (生产环境)
    DATABASE_URL: str = "postgresql+psycopg2://localhost/quant_platform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # JWT认证 - 生产环境必须设置环境变量
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # MinIO - 生产环境必须设置环境变量
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET_NAME: str = "quant-platform"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # 数据源
    TUSHARE_TOKEN: str = ""
    PRIMARY_DATA_SOURCE: str = "akshare"

    # 应用配置
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    def check_production_safety(self) -> List[str]:
        """检查生产环境安全配置，返回警告列表"""
        warnings = []
        if self.SECRET_KEY == "CHANGE_ME_IN_PRODUCTION":
            warnings.append("SECRET_KEY 未修改，请在 .env 中设置强密钥")
        if not self.MINIO_ACCESS_KEY:
            warnings.append("MINIO_ACCESS_KEY 未设置")
        if not self.MINIO_SECRET_KEY:
            warnings.append("MINIO_SECRET_KEY 未设置")
        return warnings


settings = Settings()