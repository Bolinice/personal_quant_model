"""数据质量校验 API。"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services import data_quality_service
from app.core.response import success

router = APIRouter()


@router.get("/check")
def run_quality_check(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
):
    """运行所有数据质量检查"""
    result = data_quality_service.run_all_checks(db, start_date, end_date)
    return success(result)


@router.get("/missing-days")
def check_missing_days(
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: Session = Depends(get_db),
):
    """检查缺失交易日"""
    result = data_quality_service.check_missing_trading_days(db, start_date, end_date)
    return success(result)


@router.get("/price-anomaly")
def check_price_anomaly(
    trade_date: Optional[date] = Query(None, description="交易日期"),
    db: Session = Depends(get_db),
):
    """检查价格异常"""
    result = data_quality_service.check_price_anomaly(db, trade_date)
    return success(result)


@router.get("/zero-volume")
def check_zero_volume(
    trade_date: Optional[date] = Query(None, description="交易日期"),
    db: Session = Depends(get_db),
):
    """检查成交量零值异常"""
    result = data_quality_service.check_zero_volume(db, trade_date)
    return success(result)


@router.get("/financial-consistency")
def check_financial_consistency(
    report_date: Optional[date] = Query(None, description="报告日期"),
    db: Session = Depends(get_db),
):
    """检查财务数据勾稽关系"""
    result = data_quality_service.check_financial_consistency(db, report_date)
    return success(result)