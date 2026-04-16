from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    celery_broker_url: str
    celery_result_backend: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_name: str
    debug: bool = False
    cors_origins: str = ""
    redis_host: str = "localhost"
    redis_port: int = 6379

    # 数据源配置
    tushare_token: str = ""
    primary_data_source: str = "akshare"  # tushare 或 akshare

    class Config:
        # 使用绝对路径确保正确加载 .env 文件
        env_file = str(Path(__file__).parent.parent / ".env")
        env_file_encoding = "utf-8"

settings = Settings()
