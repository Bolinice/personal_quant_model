"""分析师一致预期数据模型"""

from sqlalchemy import Column, Float, Index, Integer, String, UniqueConstraint

from app.db.base_class import Base


class StockAnalystConsensus(Base):
    __tablename__ = "stock_analyst_consensus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, comment="股票代码")
    effective_date = Column(String(8), nullable=False, comment="生效日期")
    ann_date = Column(String(8), nullable=True, comment="公告日期(PIT)")
    consensus_eps_fy0 = Column(Float, nullable=True, comment="一致预期EPS(FY0)")
    consensus_eps_fy1 = Column(Float, nullable=True, comment="一致预期EPS(FY1)")
    consensus_eps_fy2 = Column(Float, nullable=True, comment="一致预期EPS(FY2)")
    analyst_coverage = Column(Integer, nullable=True, comment="分析师覆盖数")
    rating_mean = Column(Float, nullable=True, comment="平均评级(1-5)")
    target_price_mean = Column(Float, nullable=True, comment="平均目标价")

    __table_args__ = (
        UniqueConstraint("ts_code", "effective_date", name="uq_analyst_code_date"),
        Index("ix_analyst_effective_date", "effective_date"),
        Index("ix_analyst_code_date", "ts_code", "effective_date"),
    )
