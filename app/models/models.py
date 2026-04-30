from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class Model(Base):
    """模型定义表"""

    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint("model_code", name="uq_model_code"),
        Index("ix_model_type", "model_type"),
        Index("ix_model_status", "status"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_code: str = Column(String(50), unique=True, index=True, nullable=False)
    model_name: str = Column(String(100), nullable=False)
    model_type: str = Column(String(30))  # scoring, classification, regression
    description: Text = Column(Text)
    version: str = Column(String(20), default="1.0")
    status: str = Column(String(20), default="draft")  # draft, active, archived
    # 模型配置
    factor_ids: JSON = Column(JSON)  # 因子ID列表
    factor_weights: JSON = Column(JSON)  # 因子权重
    model_config: JSON = Column(JSON)  # 模型参数
    # 模型指标
    ic_mean: float = Column(Float)
    ic_ir: float = Column(Float)
    rank_ic_mean: float = Column(Float)
    rank_ic_ir: float = Column(Float)
    turnover: float = Column(Float)  # 换手率
    # 元数据
    is_default: bool = Column(Boolean, default=False)
    created_by: int = Column(Integer)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Model(id={self.id}, model_code='{self.model_code}', model_name='{self.model_name}')>"


class ModelFactorWeight(Base):
    """模型因子权重表"""

    __tablename__ = "model_factor_weights"
    __table_args__ = (
        UniqueConstraint("model_id", "factor_id", name="uq_mfw_model_factor"),
        Index("ix_mfw_model", "model_id"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    factor_id: int = Column(Integer, index=True, nullable=False)
    weight: float = Column(Float, nullable=False)
    direction: int = Column(Integer, default=1)  # 1正向, -1反向
    is_active: bool = Column(Boolean, default=True)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelScore(Base):
    """模型评分结果表"""

    __tablename__ = "model_scores"
    __table_args__ = (
        UniqueConstraint("model_id", "security_id", "trade_date", name="uq_ms_model_sec_date"),
        Index("ix_ms_model_date", "model_id", "trade_date"),
        Index("ix_ms_security_date", "security_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    security_id: str = Column(String(20), index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    score: float = Column(Float)  # 综合得分
    rank: int = Column(Integer)  # 排名
    quantile: int = Column(Integer)  # 分位
    is_selected: bool = Column(Boolean, default=False)  # 是否入选
    factor_contributions: JSON = Column(JSON)  # 各因子贡献度
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<ModelScore(model_id={self.model_id}, security_id={self.security_id}, score={self.score})>"


class ModelPerformance(Base):
    """模型表现跟踪表"""

    __tablename__ = "model_performance"
    __table_args__ = (
        UniqueConstraint("model_id", "trade_date", name="uq_mp_model_date"),
        Index("ix_mp_model_date", "model_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    daily_return: float = Column(Float)
    cumulative_return: float = Column(Float)
    max_drawdown: float = Column(Float)
    sharpe_ratio: float = Column(Float)
    ic: float = Column(Float)
    rank_ic: float = Column(Float)
    turnover: float = Column(Float)
    num_selected: int = Column(Integer)
    created_at: DateTime = Column(DateTime, server_default=func.now())
