from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.sql import func
from app.db.base import Base


class SimulatedPortfolio(Base):
    """模拟组合主表"""
    __tablename__ = "simulated_portfolios"
    __table_args__ = (
        Index("ix_sp_model", "model_id"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    name: str = Column(String(100), nullable=False)
    benchmark_code: str = Column(String(20))
    start_date: Date = Column(Date)
    initial_capital: float = Column(Float, default=1000000.0)
    current_value: float = Column(Float)
    status: str = Column(String(20), default="running")  # running, stopped
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SimulatedPortfolio(id={self.id}, model_id={self.model_id}, name='{self.name}')>"


class SimulatedPortfolioPosition(Base):
    """模拟持仓表"""
    __tablename__ = "simulated_portfolio_positions"
    __table_args__ = (
        Index("ix_spp_portfolio_date", "portfolio_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    portfolio_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, nullable=False)
    security_id: str = Column(String(20), nullable=False)
    weight: float = Column(Float)
    shares: int = Column(Integer)
    market_value: float = Column(Float)
    created_at: DateTime = Column(DateTime, server_default=func.now())


class SimulatedPortfolioNav(Base):
    """模拟净值表"""
    __tablename__ = "simulated_portfolio_navs"
    __table_args__ = (
        Index("ix_spn_portfolio_date", "portfolio_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    portfolio_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, nullable=False)
    nav: float = Column(Float)
    benchmark_nav: float = Column(Float)
    excess_nav: float = Column(Float)
    drawdown: float = Column(Float)
    created_at: DateTime = Column(DateTime, server_default=func.now())