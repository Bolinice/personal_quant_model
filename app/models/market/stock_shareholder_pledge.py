"""股权质押数据模型"""
from sqlalchemy import Column, Integer, String, Float, UniqueConstraint, Index
from app.db.base import Base


class StockShareholderPledge(Base):
    __tablename__ = "stock_shareholder_pledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment='股票代码')
    trade_date = Column(String(8), nullable=False, comment='交易日期')
    pledge_ratio = Column(Float, nullable=True, comment='质押比例(%)')
    total_pledge_shares = Column(Float, nullable=True, comment='质押总股数(股)')
    total_shares = Column(Float, nullable=True, comment='总股本(股)')
    pledgor_count = Column(Integer, nullable=True, comment='质押股东数')

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_pledge_code_date"),
        Index("ix_pledge_trade_date", "trade_date"),
        Index("ix_pledge_code_date", "ts_code", "trade_date"),
    )