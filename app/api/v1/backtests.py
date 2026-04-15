from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.services.backtests_service import get_backtests, create_backtest, update_backtest, get_backtest_results, create_backtest_result, get_backtest_trades, run_backtest, cancel_backtest
from app.models.backtests import Backtest, BacktestResult, BacktestTrade
from app.schemas.backtests import BacktestCreate, BacktestUpdate, BacktestResultCreate, BacktestOut, BacktestResultOut, BacktestTradeOut

router = APIRouter()

@router.get("/", response_model=list[BacktestOut])
def read_backtests(model_id: int = None, status: str = None, skip: int = 0, limit: int = 100, db: Session = Depends(SessionLocal)):
    backtests = get_backtests(model_id=model_id, status=status, skip=skip, limit=limit, db=db)
    return backtests

@router.post("/", response_model=BacktestOut)
def create_backtest_endpoint(backtest: BacktestCreate, db: Session = Depends(SessionLocal)):
    return create_backtest(backtest, db=db)

@router.get("/{backtest_id}", response_model=BacktestOut)
def read_backtest(backtest_id: int, db: Session = Depends(SessionLocal)):
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return backtest

@router.put("/{backtest_id}", response_model=BacktestOut)
def update_backtest_endpoint(backtest_id: int, backtest_update: BacktestUpdate, db: Session = Depends(SessionLocal)):
    backtest = update_backtest(backtest_id, backtest_update, db=db)
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return backtest

@router.get("/{backtest_id}/result", response_model=BacktestResultOut)
def read_backtest_result(backtest_id: int, db: Session = Depends(SessionLocal)):
    result = get_backtest_results(backtest_id, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    return result

@router.post("/{backtest_id}/result", response_model=BacktestResultOut)
def create_backtest_result_endpoint(backtest_id: int, result: BacktestResultCreate, db: Session = Depends(SessionLocal)):
    return create_backtest_result(backtest_id, result, db=db)

@router.get("/{backtest_id}/trades", response_model=list[BacktestTradeOut])
def read_backtest_trades(backtest_id: int, page: int = 1, page_size: int = 100, db: Session = Depends(SessionLocal)):
    trades = get_backtest_trades(backtest_id, page=page, page_size=page_size, db=db)
    return trades

@router.post("/{backtest_id}/run", response_model=BacktestOut)
def run_backtest_endpoint(backtest_id: int, db: Session = Depends(SessionLocal)):
    backtest = run_backtest(backtest_id, db=db)
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found or failed to run")
    return backtest

@router.post("/{backtest_id}/cancel", response_model=BacktestOut)
def cancel_backtest_endpoint(backtest_id: int, db: Session = Depends(SessionLocal)):
    success = cancel_backtest(backtest_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Backtest not found")
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    return backtest
