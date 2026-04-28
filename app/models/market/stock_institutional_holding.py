"""机构持仓数据模型"""

from sqlalchemy import Column, Float, Index, Integer, String, UniqueConstraint

from app.db.base import Base


class StockInstitutionalHolding(Base):
    __tablename__ = "stock_institutional_holding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment="股票代码")
    trade_date = Column(String(8), nullable=False, comment="交易日期/报告期")
    ann_date = Column(String(8), nullable=True, comment="公告日期(PIT)")
    hold_amount = Column(Float, nullable=True, comment="机构持有股数(股)")
    hold_ratio = Column(Float, nullable=True, comment="机构持股比例(%)")
    change_amount = Column(Float, nullable=True, comment="机构持股变化(股)")

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_inst_holding_code_date"),
        Index("ix_inst_holding_trade_date", "trade_date"),
        Index("ix_inst_holding_code_date", "ts_code", "trade_date"),
    )
