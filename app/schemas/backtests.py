from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date

class BacktestBase(BaseModel):
    model_id: int
    job_name: str
    benchmark_code: str
    start_date: date
    end_date: date
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    slippage_rate: float = 0.0005

class BacktestCreate(BacktestBase):
    pass

class BacktestUpdate(BaseModel):
    status: Optional[str] = None
    result_path: Optional[str] = None

class BacktestInDB(BacktestBase):
    id: int
    status: str
    result_path: Optional[str]
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class BacktestOut(BacktestBase):
    id: int
    status: str
    result_path: Optional[str]
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class BacktestResultBase(BaseModel):
    backtest_id: int
    total_return: float
    annual_return: float
    benchmark_return: float
    excess_return: float
    max_drawdown: float
    sharpe: float
    calmar: float
    information_ratio: float
    turnover_rate: float
    result_data: Optional[Dict[str, Any]] = None

class BacktestResultCreate(BacktestResultBase):
    pass

class BacktestResultInDB(BacktestResultBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class BacktestResultOut(BacktestResultBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class BacktestTradeBase(BaseModel):
    backtest_id: int
    trade_date: date
    security_id: int
    trade_type: str
    price: float
    quantity: int
    amount: float

class BacktestTradeCreate(BacktestTradeBase):
    pass

class BacktestTradeInDB(BacktestTradeBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class BacktestTradeOut(BacktestTradeBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
