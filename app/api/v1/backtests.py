"""回测管理 API。"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.backtests import Backtest
from app.services.backtests_service import (
    get_backtests, create_backtest, update_backtest,
    get_backtest_results, run_backtest, cancel_backtest,
)
from app.schemas.backtests import BacktestCreate, BacktestUpdate, BacktestOut, BacktestResultOut
from app.core.response import success, error

router = APIRouter()


@router.get("/")
def read_backtests(model_id: int = None, status: str = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取回测列表"""
    backtests = get_backtests(model_id=model_id, status=status, skip=skip, limit=limit, db=db)
    return success(backtests)


@router.get("/{backtest_id}")
def read_backtest(backtest_id: int, db: Session = Depends(get_db)):
    """获取回测详情"""
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return success(backtest)


@router.post("/")
def create_backtest_endpoint(backtest: BacktestCreate, db: Session = Depends(get_db)):
    """创建回测"""
    result = create_backtest(backtest, db=db)
    return success(result)


@router.put("/{backtest_id}")
def update_backtest_endpoint(backtest_id: int, backtest_update: BacktestUpdate, db: Session = Depends(get_db)):
    """更新回测"""
    result = update_backtest(backtest_id, backtest_update, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return success(result)


@router.get("/{backtest_id}/results")
def read_backtest_results(backtest_id: int, db: Session = Depends(get_db)):
    """获取回测结果"""
    results = get_backtest_results(backtest_id, db=db)
    return success(results)


@router.post("/{backtest_id}/run")
def run_backtest_endpoint(backtest_id: int, db: Session = Depends(get_db)):
    """运行回测"""
    result = run_backtest(backtest_id, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest not found or failed to run")
    return success(result)


@router.post("/{backtest_id}/cancel")
def cancel_backtest_endpoint(backtest_id: int, db: Session = Depends(get_db)):
    """取消回测"""
    cancelled = cancel_backtest(backtest_id, db=db)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Backtest not found")
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    return success(backtest)