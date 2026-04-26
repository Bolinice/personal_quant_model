"""组合管理 API。"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.services.portfolios_service import get_portfolios, create_portfolio, get_portfolio_positions, create_portfolio_positions, get_rebalance_records, create_rebalance_record, generate_research_snapshot, generate_change_observation
from app.schemas.portfolios import PortfolioCreate, PortfolioUpdate, PortfolioOut, PortfolioPositionCreate, PortfolioPositionOut, RebalanceRecordCreate, RebalanceRecordOut
from app.core.response import success, error
from app.core.permissions import require_permission
from app.core.compliance import add_disclaimer

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
    return add_disclaimer(success(positions))


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


@router.post("/research-snapshot")
def generate_research_snapshot_endpoint(
    model_id: int,
    trade_date: str,
    current_user: User = Depends(require_permission("portfolio_track")),
    db: Session = Depends(get_db),
):
    """生成研究组合快照（原 generate_portfolio，合规化改名）"""
    portfolio = generate_research_snapshot(model_id, trade_date, db=db)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="研究组合快照生成失败")
    return add_disclaimer(success(portfolio))


@router.post("/change-observation")
def generate_change_observation_endpoint(
    model_id: int,
    trade_date: str,
    current_user: User = Depends(require_permission("portfolio_change_observe")),
    db: Session = Depends(get_db),
):
    """生成结构变化观察（原 generate_rebalance，合规化改名）"""
    record = generate_change_observation(model_id, trade_date, db=db)
    if record is None:
        raise HTTPException(status_code=404, detail="结构变化观察生成失败")
    return add_disclaimer(success(record))