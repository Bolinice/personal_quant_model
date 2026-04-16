from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.performance_service import get_performance_analysis, get_industry_exposure, get_style_exposure, generate_performance_report
from app.schemas.performance import PerformanceAnalysis, PerformanceReport
from app.models.backtests import BacktestResult

router = APIRouter()

@router.get("/backtests/{backtest_id}/analysis", response_model=PerformanceAnalysis)
def get_backtest_performance(backtest_id: int, start_date: str = None, end_date: str = None, db: Session = Depends(get_db)):
    analysis = get_performance_analysis(backtest_id, start_date, end_date, db=db)
    if not analysis:
        raise HTTPException(status_code=404, detail="Performance analysis not found")
    return analysis

@router.get("/backtests/{backtest_id}/industry-exposure", response_model=Dict[str, float])
def get_backtest_industry_exposure(backtest_id: int, date: str, db: Session = Depends(get_db)):
    exposure = get_industry_exposure(backtest_id, date, db=db)
    if not exposure:
        raise HTTPException(status_code=404, detail="Industry exposure data not found")
    return exposure

@router.get("/backtests/{backtest_id}/style-exposure", response_model=Dict[str, float])
def get_backtest_style_exposure(backtest_id: int, date: str, db: Session = Depends(get_db)):
    exposure = get_style_exposure(backtest_id, date, db=db)
    if not exposure:
        raise HTTPException(status_code=404, detail="Style exposure data not found")
    return exposure

@router.post("/backtests/{backtest_id}/generate-report", response_model=PerformanceReport)
def generate_backtest_report(backtest_id: int, db: Session = Depends(get_db)):
    # 获取回测结果
    result = db.query(BacktestResult).filter(BacktestResult.backtest_id == backtest_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    # 获取绩效分析
    analysis = get_performance_analysis(backtest_id, db=db)
    if not analysis:
        raise HTTPException(status_code=404, detail="Performance analysis not found")

    # 生成报告
    report = generate_performance_report(analysis)

    return report

@router.get("/simulated-portfolios/{portfolio_id}/analysis", response_model=PerformanceAnalysis)
def get_portfolio_performance(portfolio_id: int, start_date: str = None, end_date: str = None, db: Session = Depends(get_db)):
    # 这里需要实现模拟组合的绩效分析
    # 暂时使用回测的绩效分析作为示例
    return get_backtest_performance(portfolio_id, start_date, end_date, db=db)