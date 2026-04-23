"""绩效分析 API。"""

from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.performance_service import get_performance_analysis, get_industry_exposure, get_style_exposure, generate_performance_report
from app.schemas.performance import PerformanceAnalysis, PerformanceReport
from app.models.backtests import BacktestResult
from app.core.response import success, error

router = APIRouter()


@router.get("/backtests/{backtest_id}/analysis")
def get_backtest_performance(backtest_id: int, start_date: str = None, end_date: str = None, db: Session = Depends(get_db)):
    """获取回测绩效分析"""
    analysis = get_performance_analysis(backtest_id, start_date, end_date, db=db)
    if not analysis:
        raise HTTPException(status_code=404, detail="Performance analysis not found")
    return success(analysis)


@router.get("/backtests/{backtest_id}/industry-exposure")
def get_backtest_industry_exposure(backtest_id: int, date: str, db: Session = Depends(get_db)):
    """获取行业暴露度"""
    exposure = get_industry_exposure(backtest_id, date, db=db)
    if not exposure:
        raise HTTPException(status_code=404, detail="Industry exposure data not found")
    return success(exposure)


@router.get("/backtests/{backtest_id}/style-exposure")
def get_backtest_style_exposure(backtest_id: int, date: str, db: Session = Depends(get_db)):
    """获取风格暴露度"""
    exposure = get_style_exposure(backtest_id, date, db=db)
    if not exposure:
        raise HTTPException(status_code=404, detail="Style exposure data not found")
    return success(exposure)


@router.post("/backtests/{backtest_id}/generate-report")
def generate_backtest_report(backtest_id: int, db: Session = Depends(get_db)):
    """生成回测绩效报告"""
    result = db.query(BacktestResult).filter(BacktestResult.backtest_id == backtest_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    analysis = get_performance_analysis(backtest_id, db=db)
    if not analysis:
        raise HTTPException(status_code=404, detail="Performance analysis not found")

    report = generate_performance_report(analysis)
    return success(report)


@router.get("/simulated-portfolios/{portfolio_id}/analysis")
def get_portfolio_performance(portfolio_id: int, start_date: str = None, end_date: str = None, db: Session = Depends(get_db)):
    """获取模拟组合绩效分析"""
    analysis = get_performance_analysis(portfolio_id, start_date, end_date, db=db)
    if not analysis:
        raise HTTPException(status_code=404, detail="Performance analysis not found")
    return success(analysis)