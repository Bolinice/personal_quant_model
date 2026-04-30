"""融资融券数据模型"""

from sqlalchemy import Column, Date, Index, Integer, Numeric, String, UniqueConstraint

from app.db.base_class import Base


class StockMargin(Base):
    __tablename__ = "stock_margin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment="股票代码")
    trade_date = Column(Date, nullable=False, comment="交易日期")
    margin_buy = Column(Numeric(20, 4), nullable=True, comment="融资买入额(元)")
    margin_sell = Column(Numeric(20, 4), nullable=True, comment="融券卖出额(元)")
    margin_balance = Column(Numeric(20, 4), nullable=True, comment="融资融券余额(元)")
    margin_buy_vol = Column(Numeric(20, 4), nullable=True, comment="融资买入量(股)")
    margin_sell_vol = Column(Numeric(20, 4), nullable=True, comment="融券卖出量(股)")
    margin_sell_balance = Column(Numeric(20, 4), nullable=True, comment="融券余量金额(元)")
    margin_repay = Column(Numeric(20, 4), nullable=True, comment="融资偿还额(元)")

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_margin_code_date"),
        Index("ix_margin_trade_date", "trade_date"),
        Index("ix_margin_code_date", "ts_code", "trade_date"),
    )
