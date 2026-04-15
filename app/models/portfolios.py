from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Portfolio(Base):
    __tablename__ = "portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    trade_date = Column(DateTime, index=True)
    target_exposure = Column(Float)  # 仓位比例 0-1
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<Portfolio(id={self.id}, model_id={self.model_id}, trade_date='{self.trade_date}')>"

class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, index=True)
    security_id = Column(Integer, index=True)
    weight = Column(Float)  # 权重
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<PortfolioPosition(portfolio_id={self.portfolio_id}, security_id={self.security_id}, weight={self.weight})>"

class RebalanceRecord(Base):
    __tablename__ = "rebalance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    trade_date = Column(DateTime, index=True)
    rebalance_type = Column(String(20))  # scheduled, signal, risk
    buy_list = Column(JSON)  # 购买列表
    sell_list = Column(JSON)  # 卖出列表
    total_turnover = Column(Float)  # 总换手率
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<RebalanceRecord(model_id={self.model_id}, trade_date='{self.trade_date}', rebalance_type='{self.rebalance_type}')>"
