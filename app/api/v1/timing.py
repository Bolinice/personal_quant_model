"""择时管理 API。"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.timing_service import get_timing_signals, create_timing_signal, get_timing_config, create_timing_config, update_timing_config, calculate_ma_timing, calculate_breadth_timing, calculate_volatility_timing
from app.schemas.timing import TimingSignalCreate, TimingConfigCreate, TimingConfigUpdate, TimingSignalOut, TimingConfigOut
from app.core.response import success, error

router = APIRouter()


@router.get("/signals")
def read_timing_signals(model_id: int, start_date: str, end_date: str, db: Session = Depends(get_db)):
    """获取择时信号"""
    signals = get_timing_signals(model_id, start_date, end_date, db=db)
    return success(signals)


@router.post("/signals")
def create_timing_signal_endpoint(signal: TimingSignalCreate, db: Session = Depends(get_db)):
    """创建择时信号"""
    result = create_timing_signal(signal, db=db)
    return success(result)


@router.get("/config")
def read_timing_config(model_id: int, db: Session = Depends(get_db)):
    """获取择时配置"""
    config = get_timing_config(model_id, db=db)
    if config is None:
        raise HTTPException(status_code=404, detail="Timing config not found")
    return success(config)


@router.post("/config")
def create_timing_config_endpoint(config: TimingConfigCreate, db: Session = Depends(get_db)):
    """创建择时配置"""
    result = create_timing_config(config, db=db)
    return success(result)


@router.put("/config")
def update_timing_config_endpoint(model_id: int, config_update: TimingConfigUpdate, db: Session = Depends(get_db)):
    """更新择时配置"""
    config = update_timing_config(model_id, config_update, db=db)
    if config is None:
        raise HTTPException(status_code=404, detail="Timing config not found")
    return success(config)


@router.post("/ma-signal")
def calculate_ma_timing_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    """计算均线择时信号"""
    signal = calculate_ma_timing(model_id, trade_date, db=db)
    if signal is None:
        raise HTTPException(status_code=404, detail="MA timing signal calculation failed")
    result = create_timing_signal(signal, db=db)
    return success(result)


@router.post("/breadth-signal")
def calculate_breadth_timing_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    """计算广度择时信号"""
    signal = calculate_breadth_timing(model_id, trade_date, db=db)
    if signal is None:
        raise HTTPException(status_code=404, detail="Breadth timing signal calculation failed")
    result = create_timing_signal(signal, db=db)
    return success(result)


@router.post("/volatility-signal")
def calculate_volatility_timing_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    """计算波动率择时信号"""
    signal = calculate_volatility_timing(model_id, trade_date, db=db)
    if signal is None:
        raise HTTPException(status_code=404, detail="Volatility timing signal calculation failed")
    result = create_timing_signal(signal, db=db)
    return success(result)