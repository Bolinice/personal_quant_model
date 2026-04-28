"""分析师PIT表"""

from sqlalchemy import BigInteger, Column, Date, Integer, Numeric, String

from app.db.base_class import Base


class AnalystEstimatesPIT(Base):
    """分析师PIT表 - 一致预期EPS/覆盖度/评级"""

    __tablename__ = "analyst_estimates_pit"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(BigInteger, nullable=False, index=True, comment="股票ID")
    effective_date = Column(Date, nullable=False, comment="生效日期")
    announce_date = Column(Date, comment="公告日")
    consensus_eps_fy0 = Column(Numeric(20, 6), comment="一致预期EPS(FY0)")
    consensus_eps_fy1 = Column(Numeric(20, 6), comment="一致预期EPS(FY1)")
    analyst_coverage = Column(Integer, comment="分析师覆盖数")
    rating_mean = Column(Numeric(10, 6), comment="平均评级")
    snapshot_id = Column(String(50), index=True, comment="快照ID")

    __table_args__ = ({"comment": "分析师PIT表"},)
