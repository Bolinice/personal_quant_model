from pydantic_settings import BaseSettings
from typing import Optional

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

    class Config:
        env_file = "app/.env"

settings = Settings()
