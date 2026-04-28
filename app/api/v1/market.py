"""市场数据 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.schemas.market import IndexDailyCreate, StockDailyCreate
from app.services.market_service import (
    create_index_daily,
    create_stock_daily,
    get_index_daily,
    get_stock_daily,
)

router = APIRouter()


@router.get("/stock-daily")
def read_stock_daily(ts_code: str, start_date: str, end_date: str, db: Session = Depends(get_db)):
    """获取股票日线行情"""
    stock_data = get_stock_daily(ts_code, start_date, end_date, db=db)
    if not stock_data:
        raise HTTPException(status_code=404, detail="Stock data not found")
    return success(stock_data)


@router.get("/index-daily")
def read_index_daily(index_code: str, start_date: str, end_date: str, db: Session = Depends(get_db)):
    """获取指数日线行情"""
    index_data = get_index_daily(index_code, start_date, end_date, db=db)
    if not index_data:
        raise HTTPException(status_code=404, detail="Index data not found")
    return success(index_data)


@router.post("/stock-daily")
def create_stock_daily_endpoint(stock_data: StockDailyCreate, db: Session = Depends(get_db)):
    """创建股票日线数据"""
    result = create_stock_daily(stock_data, db=db)
    return success(result)


@router.post("/index-daily")
def create_index_daily_endpoint(index_data: IndexDailyCreate, db: Session = Depends(get_db)):
    """创建指数日线数据"""
    result = create_index_daily(index_data, db=db)
    return success(result)
