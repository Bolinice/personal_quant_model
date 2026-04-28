"""投资组合工具函数"""

from sqlalchemy.orm import Session

from app.db.base import with_db
from app.models.portfolios import PortfolioPosition
from app.models.simulated_portfolios import SimulatedPortfolio, SimulatedPortfolioNav


@with_db
def create_simulated_portfolio(data: dict, db: Session = None) -> SimulatedPortfolio:
    """创建模拟组合"""
    portfolio = SimulatedPortfolio(**data)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


@with_db
def get_portfolio_positions(
    portfolio_id: int, trade_date: str | None = None, db: Session = None
) -> list[PortfolioPosition]:
    """获取组合持仓"""
    query = db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio_id)
    # trade_date 参数暂时忽略，因为 PortfolioPosition 模型可能没有该字段
    return query.all()


@with_db
def update_portfolio_nav(portfolio_id: int, nav: float, trade_date: str, db: Session = None) -> SimulatedPortfolioNav:
    """更新组合净值"""
    nav_record = SimulatedPortfolioNav(portfolio_id=portfolio_id, trade_date=trade_date, nav=nav)
    db.add(nav_record)
    db.commit()
    db.refresh(nav_record)
    return nav_record


@with_db
def get_portfolio_nav_history(
    portfolio_id: int, start_date: str, end_date: str, db: Session = None
) -> list[SimulatedPortfolioNav]:
    """获取组合净值历史"""
    return (
        db.query(SimulatedPortfolioNav)
        .filter(
            SimulatedPortfolioNav.portfolio_id == portfolio_id,
            SimulatedPortfolioNav.trade_date >= start_date,
            SimulatedPortfolioNav.trade_date <= end_date,
        )
        .order_by(SimulatedPortfolioNav.trade_date)
        .all()
    )
