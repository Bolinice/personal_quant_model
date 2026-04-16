from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.portfolios import Portfolio, PortfolioPosition
from app.models.models import Model
from app.models.stock_pools import StockPool
from app.schemas.portfolios import PortfolioCreate
from app.core.trading_utils import get_stock_price

def create_simulated_portfolio(portfolio_data: PortfolioCreate, db: Session = None):
    """创建模拟组合"""
    if db is None:
        db = SessionLocal()
        try:
            db_portfolio = Portfolio(**portfolio_data.model_dump())
            db.add(db_portfolio)
            db.commit()
            db.refresh(db_portfolio)
            return db_portfolio
        finally:
            db.close()

    db_portfolio = Portfolio(**portfolio_data.model_dump())
    db.add(db_portfolio)
    db.commit()
    db.refresh(db_portfolio)
    return db_portfolio

def get_portfolio_positions(portfolio_id: int, current_date, db: Session = None):
    """获取组合持仓"""
    if db is None:
        db = SessionLocal()
        try:
            return db.query(PortfolioPosition).filter(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.start_date <= current_date,
                PortfolioPosition.end_date >= current_date
            ).all()
        finally:
            db.close()

    return db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_id == portfolio_id,
        PortfolioPosition.start_date <= current_date,
        PortfolioPosition.end_date >= current_date
    ).all()

def generate_portfolio(model_id: int, current_date, db: Session = None):
    """生成新的投资组合（简化版本）"""
    # 这里应该实现实际的组合生成逻辑
    # 包括因子选股、权重分配等
    return None

def record_rebalance(portfolio_id: int, orders: list, current_date, db: Session = None):
    """记录调仓信息"""
    # 这里应该实现实际的调仓记录逻辑
    pass
