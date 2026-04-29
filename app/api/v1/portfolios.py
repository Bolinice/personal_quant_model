"""组合管理 API。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from app.core.compliance import add_disclaimer
from app.core.permissions import require_permission
from app.core.response import success
from app.db.base import get_db
from app.services.portfolios_service import (
    create_portfolio,
    create_portfolio_positions,
    generate_change_observation,
    generate_research_snapshot,
    get_portfolio_positions,
    get_portfolios,
    get_rebalance_records,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.user import User
    from app.schemas.portfolios import (
        PortfolioCreate,
        PortfolioPositionCreate,
    )

router = APIRouter()


@router.get("/")
def read_portfolios(model_id: int, trade_date: str | None = None, db: Session = Depends(get_db)):
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
def create_portfolio_positions_endpoint(
    portfolio_id: int, positions: list[PortfolioPositionCreate], db: Session = Depends(get_db)
):
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
