"""组合管理 API。"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.portfolios_service import get_portfolios, create_portfolio, get_portfolio_positions, create_portfolio_positions, get_rebalance_records, create_rebalance_record, generate_portfolio, generate_rebalance
from app.schemas.portfolios import PortfolioCreate, PortfolioUpdate, PortfolioOut, PortfolioPositionCreate, PortfolioPositionOut, RebalanceRecordCreate, RebalanceRecordOut
from app.core.response import success, error

router = APIRouter()


@router.get("/")
def read_portfolios(model_id: int, trade_date: str = None, db: Session = Depends(get_db)):
    """获取组合列表"""
    portfolios = get_portfolios(model_id, trade_date, db=db)
    return success(portfolios)


@router.post("/")
def create_portfolio_endpoint(portfolio: PortfolioCreate, db: Session = Depends(get_db)):
    """创建组合"""
    result = create_portfolio(portfolio, db=db)
    return success(result)


@router.get("/{portfolio_id}/positions")
def read_portfolio_positions(portfolio_id: int, db: Session = Depends(get_db)):
    """获取组合持仓"""
    positions = get_portfolio_positions(portfolio_id, db=db)
    return success(positions)


@router.post("/{portfolio_id}/positions")
def create_portfolio_positions_endpoint(portfolio_id: int, positions: List[PortfolioPositionCreate], db: Session = Depends(get_db)):
    """创建组合持仓"""
    result = create_portfolio_positions(portfolio_id, positions, db=db)
    return success(result)


@router.get("/rebalances")
def read_rebalance_records(model_id: int, start_date: str, end_date: str, db: Session = Depends(get_db)):
    """获取调仓记录"""
    records = get_rebalance_records(model_id, start_date, end_date, db=db)
    return success(records)


@router.post("/generate")
def generate_portfolio_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    """生成组合"""
    portfolio = generate_portfolio(model_id, trade_date, db=db)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio generation failed")
    return success(portfolio)


@router.post("/rebalance")
def generate_rebalance_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    """生成调仓"""
    record = generate_rebalance(model_id, trade_date, db=db)
    if record is None:
        raise HTTPException(status_code=404, detail="Rebalance generation failed")
    return success(record)