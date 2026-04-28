"""行业级别数据模型"""

from sqlalchemy import Column, Date, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class IndustryDaily(Base):
    """行业日线数据 - 行业动量/资金流/估值"""

    __tablename__ = "industry_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    industry_code = Column(String(20), nullable=False, comment="行业代码")
    industry_name = Column(String(50), nullable=True, comment="行业名称")
    trade_date = Column(Date, nullable=False, comment="交易日期")
    industry_return_1m = Column(Float, nullable=True, comment="行业1月收益率")
    industry_net_inflow = Column(Float, nullable=True, comment="行业净资金流入(万元)")
    industry_pe = Column(Float, nullable=True, comment="行业PE")
    industry_pe_mean_3y = Column(Float, nullable=True, comment="行业3年PE均值")
    industry_pb = Column(Float, nullable=True, comment="行业PB")
    industry_turnover = Column(Float, nullable=True, comment="行业换手率")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("industry_code", "trade_date", name="uq_industry_daily_code_date"),
        Index("ix_industry_daily_date", "trade_date"),
        Index("ix_industry_daily_code_date", "industry_code", "trade_date"),
    )
