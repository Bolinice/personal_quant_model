"""个股资金流向数据模型"""

from sqlalchemy import Column, Float, Index, Integer, String, UniqueConstraint

from app.db.base_class import Base


class StockMoneyFlow(Base):
    __tablename__ = "stock_money_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment="股票代码")
    trade_date = Column(String(8), nullable=False, comment="交易日期")
    smart_net_inflow = Column(Float, nullable=True, comment="主力净流入(元)")
    smart_net_pct = Column(Float, nullable=True, comment="主力净占比(%)")
    super_large_net_inflow = Column(Float, nullable=True, comment="超大单净流入(元)")
    super_large_net_pct = Column(Float, nullable=True, comment="超大单净占比(%)")
    large_net_inflow = Column(Float, nullable=True, comment="大单净流入(元)")
    large_net_pct = Column(Float, nullable=True, comment="大单净占比(%)")
    medium_net_inflow = Column(Float, nullable=True, comment="中单净流入(元)")
    medium_net_pct = Column(Float, nullable=True, comment="中单净占比(%)")
    small_net_inflow = Column(Float, nullable=True, comment="小单净流入(元)")
    small_net_pct = Column(Float, nullable=True, comment="小单净占比(%)")

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_money_flow_code_date"),
        Index("ix_money_flow_trade_date", "trade_date"),
        Index("ix_money_flow_code_date", "ts_code", "trade_date"),
    )
