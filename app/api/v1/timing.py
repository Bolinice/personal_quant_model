from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.timing_service import get_timing_signals, create_timing_signal, get_timing_config, create_timing_config, update_timing_config, calculate_ma_timing, calculate_breadth_timing, calculate_volatility_timing
from app.models.portfolios import TimingSignal, TimingConfig
from app.schemas.timing import TimingSignalCreate, TimingConfigCreate, TimingConfigUpdate, TimingSignalOut, TimingConfigOut

router = APIRouter()

@router.get("/signals", response_model=List[TimingSignalOut])
def read_timing_signals(model_id: int, start_date: str, end_date: str, db: Session = Depends(get_db)):
    signals = get_timing_signals(model_id, start_date, end_date, db=db)
    return signals

@router.post("/signals", response_model=TimingSignalOut)
def create_timing_signal_endpoint(signal: TimingSignalCreate, db: Session = Depends(get_db)):
    return create_timing_signal(signal, db=db)

@router.get("/config", response_model=TimingConfigOut)
def read_timing_config(model_id: int, db: Session = Depends(get_db)):
    config = get_timing_config(model_id, db=db)
    if config is None:
        raise HTTPException(status_code=404, detail="Timing config not found")
    return config

@router.post("/config", response_model=TimingConfigOut)
def create_timing_config_endpoint(config: TimingConfigCreate, db: Session = Depends(get_db)):
    return create_timing_config(config, db=db)

@router.put("/config", response_model=TimingConfigOut)
def update_timing_config_endpoint(model_id: int, config_update: TimingConfigUpdate, db: Session = Depends(get_db)):
    config = update_timing_config(model_id, config_update, db=db)
    if config is None:
        raise HTTPException(status_code=404, detail="Timing config not found")
    return config

@router.post("/ma-signal", response_model=TimingSignalOut)
def calculate_ma_timing_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    signal = calculate_ma_timing(model_id, trade_date, db=db)
    if signal is None:
        raise HTTPException(status_code=404, detail="MA timing signal calculation failed")
    return create_timing_signal(signal, db=db)

@router.post("/breadth-signal", response_model=TimingSignalOut)
def calculate_breadth_timing_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    signal = calculate_breadth_timing(model_id, trade_date, db=db)
    if signal is None:
        raise HTTPException(status_code=404, detail="Breadth timing signal calculation failed")
    return create_timing_signal(signal, db=db)

@router.post("/volatility-signal", response_model=TimingSignalOut)
def calculate_volatility_timing_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    signal = calculate_volatility_timing(model_id, trade_date, db=db)
    if signal is None:
        raise HTTPException(status_code=404, detail="Volatility timing signal calculation failed")
    return create_timing_signal(signal, db=db)
