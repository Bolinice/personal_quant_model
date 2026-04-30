from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class StockStatusDaily(Base):
    """股票状态日表 - 支持按交易日回放"""

    __tablename__ = "stock_status_daily"
    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_ssd_code_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    is_st = Column(Boolean, default=False)
    is_star_st = Column(Boolean, default=False)
    is_suspended = Column(Boolean, default=False)
    is_limit_up = Column(Boolean, default=False)
    is_limit_down = Column(Boolean, default=False)
    is_delist = Column(Boolean, default=False)
    risk_flag = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
