"""PIT财务表"""

from sqlalchemy import BigInteger, Column, Date, Integer, Numeric, String

from app.db.base_class import Base


class PITFinancial(Base):
    """PIT财务表 - 严格版本管理, 预告/快报/正式报表优先级"""

    __tablename__ = "pit_financial"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(BigInteger, nullable=False, index=True, comment="股票ID")
    report_period = Column(Date, nullable=False, comment="报告期")
    effective_date = Column(Date, nullable=False, comment="生效日期")
    announce_date = Column(Date, nullable=False, index=True, comment="公告日")
    source_priority = Column(Integer, default=3, comment="来源优先级: 3=正式>2=快报>1=预告")
    revision_no = Column(Integer, default=0, comment="修订版本号")
    revenue = Column(Numeric(20, 4), comment="营收")
    net_profit = Column(Numeric(20, 4), comment="净利润")
    total_assets = Column(Numeric(20, 4), comment="总资产")
    total_equity = Column(Numeric(20, 4), comment="净资产")
    operating_cashflow = Column(Numeric(20, 4), comment="经营现金流")
    gross_margin = Column(Numeric(10, 6), comment="毛利率")
    roe = Column(Numeric(12, 4), comment="ROE")
    roa = Column(Numeric(12, 4), comment="ROA")
    pe_ttm = Column(Numeric(12, 4), comment="PE")
    pb = Column(Numeric(12, 4), comment="PB")
    ps_ttm = Column(Numeric(12, 4), comment="PS")
    asset_liability_ratio = Column(Numeric(12, 4), comment="资产负债率")
    snapshot_id = Column(String(50), index=True, comment="快照ID")

    __table_args__ = ({"comment": "PIT财务表"},)
