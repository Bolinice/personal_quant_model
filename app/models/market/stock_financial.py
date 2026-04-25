"""股票财务数据模型"""
from sqlalchemy import Column, Integer, String, Float, UniqueConstraint, Index
from app.db.base import Base


class StockFinancial(Base):
    __tablename__ = "stock_financial"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # === 基础字段 ===
    ts_code = Column(String(20), nullable=False, index=True, comment='股票代码')
    ann_date = Column(String(8), nullable=True, comment='公告日期')
    end_date = Column(String(8), nullable=False, index=True, comment='报告期')

    # === 利润表字段 ===
    total_revenue = Column(Float, nullable=True, comment='营业总收入')
    operating_revenue = Column(Float, nullable=True, comment='营业收入')
    operating_cost = Column(Float, nullable=True, comment='营业成本')
    gross_profit = Column(Float, nullable=True, comment='毛利润')
    total_profit = Column(Float, nullable=True, comment='利润总额')
    net_profit = Column(Float, nullable=True, comment='净利润')
    deduct_net_profit = Column(Float, nullable=True, comment='扣除非经常性损益后的净利润')
    revenue_yoy = Column(Float, nullable=True, comment='营收同比增长率(%)')
    net_profit_yoy = Column(Float, nullable=True, comment='净利润同比增长率(%)')
    yoy_deduct_net_profit = Column(Float, nullable=True, comment='扣非净利同比增长率(%)')

    # === 资产负债表字段 ===
    total_assets = Column(Float, nullable=True, comment='总资产')
    total_equity = Column(Float, nullable=True, comment='所有者权益合计(净资产)')
    current_assets = Column(Float, nullable=True, comment='流动资产合计')
    current_liabilities = Column(Float, nullable=True, comment='流动负债合计')
    total_liabilities = Column(Float, nullable=True, comment='负债合计')

    # === 现金流量表字段 ===
    operating_cash_flow = Column(Float, nullable=True, comment='经营活动产生的现金流量净额')

    # === 财务比率字段 ===
    roe = Column(Float, nullable=True, comment='净资产收益率(%)')
    roa = Column(Float, nullable=True, comment='总资产净利率(%)')
    gross_profit_margin = Column(Float, nullable=True, comment='销售毛利率(%)')
    net_profit_margin = Column(Float, nullable=True, comment='销售净利率(%)')
    current_ratio = Column(Float, nullable=True, comment='流动比率')
    debt_to_assets = Column(Float, nullable=True, comment='资产负债率(%)')
    equity_multiplier = Column(Float, nullable=True, comment='权益乘数')

    goodwill = Column(Float, nullable=True, comment='商誉')
    # === 估值快照字段 ===
    total_market_cap = Column(Float, nullable=True, comment='总市值(万元)')
    circ_market_cap = Column(Float, nullable=True, comment='流通市值(万元)')
    pe_ttm = Column(Float, nullable=True, comment='市盈率TTM')
    pb = Column(Float, nullable=True, comment='市净率')
    ps_ttm = Column(Float, nullable=True, comment='市销率TTM')
    dividend_yield = Column(Float, nullable=True, comment='股息率(%)')

    __table_args__ = (
        UniqueConstraint("ts_code", "end_date", name="uq_financial_code_date"),
        Index("ix_financial_end_date", "end_date"),
    )
