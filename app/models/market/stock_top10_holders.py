"""前十大股东数据模型"""

from sqlalchemy import Column, Date, Index, Integer, Numeric, String, UniqueConstraint

from app.db.base_class import Base


class StockTop10Holders(Base):
    __tablename__ = "stock_top10_holders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment="股票代码")
    end_date = Column(Date, nullable=False, comment="报告期")
    ann_date = Column(Date, nullable=True, comment="公告日期(PIT)")
    holder_name = Column(String(100), nullable=True, comment="股东名称")
    hold_amount = Column(Numeric(20, 4), nullable=True, comment="持有股数(股)")
    hold_ratio = Column(Numeric(12, 4), nullable=True, comment="持股比例(%)")
    rank = Column(Integer, nullable=True, comment="排名")

    __table_args__ = (
        UniqueConstraint("ts_code", "end_date", "rank", name="uq_top10_code_date_rank"),
        Index("ix_top10_end_date", "end_date"),
        Index("ix_top10_code_date", "ts_code", "end_date"),
    )
