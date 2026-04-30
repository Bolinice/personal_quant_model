from sqlalchemy import Boolean, Column, Date, Index, Integer, Numeric, String, UniqueConstraint

from app.db.base_class import Base


class IndexDaily(Base):
    __tablename__ = "index_daily"
    __table_args__ = (
        UniqueConstraint("index_code", "trade_date", name="uq_id_code_date"),
        Index("ix_id_code_date", "index_code", "trade_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    index_code = Column(String(16), index=True)
    trade_date = Column(Date, index=True)
    open = Column(Numeric(20, 4))
    high = Column(Numeric(20, 4))
    low = Column(Numeric(20, 4))
    close = Column(Numeric(20, 4))
    pre_close = Column(Numeric(20, 4))
    change = Column(Numeric(20, 4))
    pct_chg = Column(Numeric(14, 4))
    vol = Column(Numeric(20, 4))
    amount = Column(Numeric(24, 4))
    data_source = Column(String(20))  # 数据来源: tushare/akshare/crawler
    amount_is_estimated = Column(Boolean, default=False)  # 成交额是否为估算值

    def __repr__(self):
        return f"<IndexDaily(index_code='{self.index_code}', trade_date='{self.trade_date}', close={self.close})>"
