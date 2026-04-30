from sqlalchemy import Column, Date, DateTime, Index, Integer, Numeric, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class IndexComponent(Base):
    """指数成分股历史表"""

    __tablename__ = "index_components"
    __table_args__ = (
        Index("ix_ic_code_date", "index_code", "trade_date"),
        Index("ix_ic_code_stock", "index_code", "ts_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    index_code = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    ts_code = Column(String(20), nullable=False)
    weight = Column(Numeric(10, 6))
    created_at = Column(DateTime, server_default=func.now())
