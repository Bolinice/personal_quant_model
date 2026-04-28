"""每日基本面数据模型（PE/PB/市值/换手率等）"""

from sqlalchemy import Column, Date, Float, Index, Integer, String, UniqueConstraint

from app.db.base_class import Base


class StockDailyBasic(Base):
    __tablename__ = "stock_daily_basic"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment="股票代码")
    trade_date = Column(Date, nullable=False, index=True, comment="交易日期")
    close = Column(Float, nullable=True, comment="当日收盘价")
    turnover_rate = Column(Float, nullable=True, comment="换手率(%)")
    turnover_rate_f = Column(Float, nullable=True, comment="换手率(基于自由流通股,%)")
    volume_ratio = Column(Float, nullable=True, comment="量比")
    pe = Column(Float, nullable=True, comment="市盈率(动态)")
    pe_ttm = Column(Float, nullable=True, comment="市盈率TTM")
    pb = Column(Float, nullable=True, comment="市净率")
    ps = Column(Float, nullable=True, comment="市销率")
    ps_ttm = Column(Float, nullable=True, comment="市销率TTM")
    dv_ratio = Column(Float, nullable=True, comment="股息率(%)")
    dv_ttm = Column(Float, nullable=True, comment="股息率TTM(%)")
    total_mv = Column(Float, nullable=True, comment="总市值(万元)")
    circ_mv = Column(Float, nullable=True, comment="流通市值(万元)")

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_daily_basic_code_date"),
        Index("ix_daily_basic_trade_date", "trade_date"),
        Index("ix_daily_basic_code_date", "ts_code", "trade_date"),
    )
