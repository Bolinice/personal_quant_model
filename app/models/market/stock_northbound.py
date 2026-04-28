"""北向资金数据模型"""

from sqlalchemy import Column, Float, Index, Integer, String, UniqueConstraint

from app.db.base import Base


class StockNorthbound(Base):
    __tablename__ = "stock_northbound"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment="股票代码")
    trade_date = Column(String(8), nullable=False, comment="交易日期")
    north_holding = Column(Float, nullable=True, comment="北向持股数量(股)")
    north_holding_pct = Column(Float, nullable=True, comment="北向持股占流通股比(%)")
    north_holding_mv = Column(Float, nullable=True, comment="北向持股市值(万元)")
    north_net_buy = Column(Float, nullable=True, comment="北向净买入(万元)")
    north_buy = Column(Float, nullable=True, comment="北向买入(万元)")
    north_sell = Column(Float, nullable=True, comment="北向卖出(万元)")

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_northbound_code_date"),
        Index("ix_northbound_trade_date", "trade_date"),
        Index("ix_northbound_code_date", "ts_code", "trade_date"),
    )
