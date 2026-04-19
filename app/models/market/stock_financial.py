from sqlalchemy import Column, Integer, String, DateTime, Date, Numeric, JSON, Index
from sqlalchemy.sql import func
from app.db.base import Base

class StockFinancial(Base):
    __tablename__ = "stock_financial"
    __table_args__ = (
        Index("ix_sf_code_end_date", "ts_code", "end_date"),
        Index("ix_sf_ann_date", "ann_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(16), index=True)
    ann_date = Column(Date, index=True)
    end_date = Column(Date, index=True)
    report_type = Column(String(10))
    update_flag = Column(String(10))
    revenue = Column(Numeric(24, 4))
    yoy_revenue = Column(Numeric(14, 4))
    net_profit = Column(Numeric(24, 4))
    yoy_net_profit = Column(Numeric(14, 4))
    gross_profit = Column(Numeric(24, 4))
    gross_profit_margin = Column(Numeric(10, 4))
    roe = Column(Numeric(10, 4))
    roa = Column(Numeric(10, 4))
    eps = Column(Numeric(14, 4))
    bvps = Column(Numeric(14, 4))
    net_profit_ratio = Column(Numeric(10, 4))
    current_ratio = Column(Numeric(10, 4))
    quick_ratio = Column(Numeric(10, 4))
    cash_ratio = Column(Numeric(10, 4))
    asset_liability_ratio = Column(Numeric(10, 4))
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<StockFinancial(ts_code='{self.ts_code}', ann_date='{self.ann_date}', revenue={self.revenue})>"