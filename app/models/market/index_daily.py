from sqlalchemy import Column, Integer, String, DateTime, Float, Numeric
from sqlalchemy.sql import func
from app.db.base import Base

class IndexDaily(Base):
    __tablename__ = "index_daily"

    id = Column(Integer, primary_key=True, index=True)
    index_code = Column(String(16), index=True)
    trade_date = Column(DateTime, index=True)
    open = Column(Numeric(20, 4))
    high = Column(Numeric(20, 4))
    low = Column(Numeric(20, 4))
    close = Column(Numeric(20, 4))
    pre_close = Column(Numeric(20, 4))
    change = Column(Numeric(20, 4))
    pct_chg = Column(Numeric(14, 4))
    vol = Column(Numeric(20, 4))
    amount = Column(Numeric(24, 4))

    def __repr__(self):
        return f"<IndexDaily(index_code='{self.index_code}', trade_date='{self.trade_date}', close={self.close})>"