from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Backtest(Base):
    __tablename__ = "backtests"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    job_name = Column(String(100))
    benchmark_code = Column(String(20))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    initial_capital = Column(Float)
    commission_rate = Column(Float)
    stamp_tax_rate = Column(Float)
    slippage_rate = Column(Float)
    status = Column(String(20))  # pending, running, success, failed
    result_path = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Backtest(id={self.id}, model_id={self.model_id}, job_name='{self.job_name}')>"

class BacktestResult(Base):
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, index=True)
    total_return = Column(Float)
    annual_return = Column(Float)
    benchmark_return = Column(Float)
    excess_return = Column(Float)
    max_drawdown = Column(Float)
    sharpe = Column(Float)
    calmar = Column(Float)
    information_ratio = Column(Float)
    turnover_rate = Column(Float)
    result_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<BacktestResult(backtest_id={self.backtest_id}, total_return={self.total_return})>"

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    
    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, index=True)
    trade_date = Column(DateTime)
    security_id = Column(Integer)
    trade_type = Column(String(10))  # buy, sell
    price = Column(Float)
    quantity = Column(Integer)
    amount = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<BacktestTrade(backtest_id={self.backtest_id}, trade_date='{self.trade_date}', trade_type='{self.trade_type}')>"
