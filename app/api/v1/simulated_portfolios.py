"""模拟组合 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.schemas.simulated_portfolios import (
    SimulatedPortfolioCreate,
    SimulatedPortfolioPositionCreate,
)
from app.services.simulated_portfolios_service import (
    calculate_simulated_portfolio_nav,
    create_simulated_portfolio,
    create_simulated_portfolio_positions,
    get_simulated_portfolio_navs,
    get_simulated_portfolio_positions,
    get_simulated_portfolios,
    update_simulated_portfolio,
)

router = APIRouter()


@router.get("/")
def read_simulated_portfolios(
    model_id: int | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """获取模拟组合列表"""
    portfolios = get_simulated_portfolios(model_id=model_id, skip=skip, limit=limit, db=db)
    return success(portfolios)


@router.post("/")
def create_simulated_portfolio_endpoint(portfolio: SimulatedPortfolioCreate, db: Session = Depends(get_db)):
    """创建模拟组合"""
    result = create_simulated_portfolio(portfolio, db=db)
    return success(result)


@router.get("/{portfolio_id}/positions")
def read_simulated_portfolio_positions(portfolio_id: int, trade_date: str | None = None, db: Session = Depends(get_db)):
    """获取模拟组合持仓"""
    positions = get_simulated_portfolio_positions(portfolio_id, trade_date, db=db)
    return success(positions)


@router.post("/{portfolio_id}/positions")
def create_simulated_portfolio_positions_endpoint(
    portfolio_id: int, positions: list[SimulatedPortfolioPositionCreate], db: Session = Depends(get_db)
):
    """创建模拟组合持仓"""
    result = create_simulated_portfolio_positions(portfolio_id, positions, db=db)
    return success(result)


@router.get("/{portfolio_id}/navs")
def read_simulated_portfolio_navs(
    portfolio_id: int, start_date: str | None = None, end_date: str | None = None, db: Session = Depends(get_db)
):
    """获取模拟组合净值"""
    navs = get_simulated_portfolio_navs(portfolio_id, start_date, end_date, db=db)
    return success(navs)


@router.post("/{portfolio_id}/nav")
def calculate_simulated_portfolio_nav_endpoint(portfolio_id: int, trade_date: str, db: Session = Depends(get_db)):
    """计算模拟组合净值"""
    nav = calculate_simulated_portfolio_nav(portfolio_id, trade_date, db=db)
    if nav is None:
        raise HTTPException(status_code=404, detail="NAV calculation failed")
    return success(nav)


@router.put("/{portfolio_id}")
def update_simulated_portfolio_endpoint(portfolio_id: int, updates: dict, db: Session = Depends(get_db)):
    """更新模拟组合"""
    portfolio = update_simulated_portfolio(portfolio_id, updates, db=db)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Simulated portfolio not found")
    return success(portfolio)
