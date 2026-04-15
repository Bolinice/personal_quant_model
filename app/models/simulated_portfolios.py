from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class SimulatedPortfolio(Base):
    __tablename__ = "simulated_portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    name = Column(String(100))
    benchmark_code = Column(String(20))
    start_date = Column(DateTime)
    initial_capital = Column(Float)
    current_value = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SimulatedPortfolio(id={self.id}, model_id={self.model_id}, name='{self.name}')>"

class SimulatedPortfolioPosition(Base):
    __tablename__ = "simulated_portfolio_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, index=True)
    trade_date = Column(DateTime)
    security_id = Column(Integer)
    weight = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<SimulatedPortfolioPosition(portfolio_id={self.portfolio_id}, security_id={self.security_id}, weight={self.weight})>"

class SimulatedPortfolioNav(Base):
    __tablename__ = "simulated_portfolio_navs"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, index=True)
    trade_date = Column(DateTime)
    nav = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<SimulatedPortfolioNav(portfolio_id={self.portfolio_id}, trade_date='{self.trade_date}', nav={self.nav})>"
