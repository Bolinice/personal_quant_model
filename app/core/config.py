from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field


class BacktestConfig(BaseSettings):
    """回测配置"""
    INITIAL_CAPITAL: float = 1_000_000.0
    COMMISSION_RATE: float = 0.00025
    STAMP_TAX_RATE: float = 0.001
    SLIPPAGE_RATE: float = 0.001
    MIN_COMMISSION: float = 5.0
    DEFAULT_REBALANCE_FREQ: str = "monthly"
    MAX_TURNOVER: float = 1.0
    WALK_FORWARD_TRAIN_WINDOW: int = 504
    WALK_FORWARD_TEST_WINDOW: int = 63
    WALK_FORWARD_GAP: int = 21

    model_config = {"env_prefix": "BACKTEST_", "extra": "ignore"}


class RiskConfig(BaseSettings):
    """风险模型配置"""
    COVARIANCE_HALFLIFE: int = 60
    BARRA_HALFLIFE: int = 168
    IDIOSYNCRATIC_HALFLIFE: int = 84
    SHRINKAGE_TARGET: str = "identity"
    EIGENVALUE_CLIP_PCT: float = 0.05
    VAR_CONFIDENCE: float = 0.95
    MAX_POSITION: float = 0.10
    MAX_INDUSTRY_WEIGHT: float = 0.30
    RISK_AVERSION: float = 1.0

    model_config = {"env_prefix": "RISK_", "extra": "ignore"}


class FactorConfig(BaseSettings):
    """因子配置"""
    MIN_COVERAGE: float = 0.8
    MAD_THRESHOLD: float = 3.0
    ZSCORE_CLIP: float = 3.0
    IC_MIN_STOCKS: int = 10
    FORWARD_PERIOD: int = 20
    N_GROUPS: int = 5
    MAX_DECAY_LAG: int = 20
    CACHE_TTL: int = 1800
    CACHE_MAX_SIZE: int = 10000

    model_config = {"env_prefix": "FACTOR_", "extra": "ignore"}


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
    LOG_FORMAT: str = "text"  # "text" or "json"

    # 分组配置
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    factor: FactorConfig = Field(default_factory=FactorConfig)

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
