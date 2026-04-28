from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class StockPool(Base):
    """股票池定义表"""

    __tablename__ = "stock_pools"
    __table_args__ = (UniqueConstraint("pool_code", name="uq_pool_code"),)

    id: int = Column(Integer, primary_key=True, index=True)
    pool_code: str = Column(String(50), unique=True, index=True, nullable=False)
    pool_name: str = Column(String(100), nullable=False)
    pool_type: str = Column(String(20))  # index, custom, dynamic
    base_index_code: str = Column(String(20))  # 基准指数代码
    filter_config: JSON = Column(JSON)  # 过滤规则配置
    description: str = Column(String(500))
    is_active: bool = Column(Boolean, default=True)
    created_by: int = Column(Integer)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<StockPool(id={self.id}, pool_code='{self.pool_code}', pool_name='{self.pool_name}')>"


class StockPoolSnapshot(Base):
    """股票池快照表 - 支持按日期回放"""

    __tablename__ = "stock_pool_snapshots"
    __table_args__ = (
        UniqueConstraint("pool_id", "trade_date", name="uq_pool_snapshot_date"),
        Index("ix_pool_snap_date", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    pool_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    securities: JSON = Column(JSON)  # 股票列表
    eligible_count: int = Column(Integer)  # 纳入数量
    excluded_count: int = Column(Integer)  # 剔除数量
    exclude_reasons: JSON = Column(JSON)  # 剔除原因 {ts_code: reason}
    snapshot_version: str = Column(String(20))  # 快照版本
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<StockPoolSnapshot(pool_id={self.pool_id}, trade_date='{self.trade_date}', eligible_count={self.eligible_count})>"
