"""股票财务数据模型"""

from sqlalchemy import Column, Date, Index, Integer, Numeric, String, UniqueConstraint

from app.db.base_class import Base


class StockFinancial(Base):
    __tablename__ = "stock_financial"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # === 基础字段 ===
    ts_code = Column(String(20), nullable=False, index=True, comment="股票代码")
    ann_date = Column(Date, nullable=True, comment="公告日期")
    end_date = Column(Date, nullable=False, index=True, comment="报告期")

    # === 利润表字段 ===
    total_revenue = Column(Numeric(20, 4), nullable=True, comment="营业总收入")
    operating_revenue = Column(Numeric(20, 4), nullable=True, comment="营业收入")
    operating_cost = Column(Numeric(20, 4), nullable=True, comment="营业成本")
    gross_profit = Column(Numeric(20, 4), nullable=True, comment="毛利润")
    total_profit = Column(Numeric(20, 4), nullable=True, comment="利润总额")
    net_profit = Column(Numeric(20, 4), nullable=True, comment="净利润")
    deduct_net_profit = Column(Numeric(20, 4), nullable=True, comment="扣除非经常性损益后的净利润")
    revenue_yoy = Column(Numeric(12, 4), nullable=True, comment="营收同比增长率(%)")
    net_profit_yoy = Column(Numeric(12, 4), nullable=True, comment="净利润同比增长率(%)")
    yoy_deduct_net_profit = Column(Numeric(12, 4), nullable=True, comment="扣非净利同比增长率(%)")
    operating_cash_flow = Column(Numeric(20, 4), nullable=True, comment="经营活动产生的现金流量净额")

    # === 资产负债表字段 ===
    total_assets = Column(Numeric(20, 4), nullable=True, comment="总资产")
    total_equity = Column(Numeric(20, 4), nullable=True, comment="所有者权益合计(净资产)")
    current_assets = Column(Numeric(20, 4), nullable=True, comment="流动资产合计")
    current_liabilities = Column(Numeric(20, 4), nullable=True, comment="流动负债合计")
    total_liabilities = Column(Numeric(20, 4), nullable=True, comment="负债合计")
    goodwill = Column(Numeric(20, 4), nullable=True, comment="商誉")

    # === 上期数据 (用于ROE/ROA/Sloan应计的期初值) ===
    total_equity_prev = Column(Numeric(20, 4), nullable=True, comment="上期所有者权益")
    total_assets_prev = Column(Numeric(20, 4), nullable=True, comment="上期总资产")

    # === TTM滚动数据 (用于成长因子) ===
    revenue_ttm = Column(Numeric(20, 4), nullable=True, comment="营业收入TTM")
    net_profit_ttm = Column(Numeric(20, 4), nullable=True, comment="净利润TTM")
    deduct_net_profit_ttm = Column(Numeric(20, 4), nullable=True, comment="扣非净利TTM")
    ocf_ttm = Column(Numeric(20, 4), nullable=True, comment="经营现金流TTM")
    revenue_yoy_4q = Column(Numeric(12, 4), nullable=True, comment="营收同比(4季前)")
    net_profit_yoy_4q = Column(Numeric(12, 4), nullable=True, comment="净利同比(4季前)")

    # === 多期统计 (用于盈利稳定性) ===
    net_profit_mean_8q = Column(Numeric(20, 4), nullable=True, comment="近8季净利均值")
    net_profit_std_8q = Column(Numeric(20, 4), nullable=True, comment="近8季净利标准差")

    # === 财务比率字段 ===
    roe = Column(Numeric(12, 4), nullable=True, comment="净资产收益率(%)")
    roa = Column(Numeric(12, 4), nullable=True, comment="总资产净利率(%)")
    gross_profit_margin = Column(Numeric(12, 4), nullable=True, comment="销售毛利率(%)")
    net_profit_margin = Column(Numeric(12, 4), nullable=True, comment="销售净利率(%)")
    current_ratio = Column(Numeric(12, 4), nullable=True, comment="流动比率")
    debt_to_assets = Column(Numeric(12, 4), nullable=True, comment="资产负债率(%)")
    equity_multiplier = Column(Numeric(12, 4), nullable=True, comment="权益乘数")

    # === 估值快照字段 ===
    total_market_cap = Column(Numeric(20, 4), nullable=True, comment="总市值(万元)")
    circ_market_cap = Column(Numeric(20, 4), nullable=True, comment="流通市值(万元)")
    pe_ttm = Column(Numeric(14, 4), nullable=True, comment="市盈率TTM")
    pb = Column(Numeric(14, 4), nullable=True, comment="市净率")
    ps_ttm = Column(Numeric(14, 4), nullable=True, comment="市销率TTM")
    dividend_yield = Column(Numeric(14, 4), nullable=True, comment="股息率(%)")

    __table_args__ = (
        UniqueConstraint("ts_code", "ann_date", "end_date", name="uq_financial_code_ann_end"),
        Index("ix_financial_ann_date", "ann_date"),
    )
