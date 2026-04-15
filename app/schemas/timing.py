from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date

class TimingSignalBase(BaseModel):
    model_id: int
    trade_date: date
    signal_type: str = "neutral"
    exposure: float = 1.0

class TimingSignalCreate(TimingSignalBase):
    pass

class TimingSignalInDB(TimingSignalBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class TimingSignalOut(TimingSignalBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class TimingConfigParams(BaseModel):
    ma_window: int = 120
    below_ma_exposure: float = 0.5
    breadth_threshold: float = 0.7
    volatility_window: int = 20
    volatility_threshold: float = 0.02

class TimingConfigBase(BaseModel):
    model_id: int
    config_type: str = "ma_timing"
    config_params: Optional[Dict[str, Any]] = None

class TimingConfigCreate(TimingConfigBase):
    pass

class TimingConfigUpdate(BaseModel):
    config_type: Optional[str] = None
    config_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class TimingConfigInDB(TimingConfigBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class TimingConfigOut(TimingConfigBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True
