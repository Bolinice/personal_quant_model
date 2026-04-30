from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class BacktestBase(BaseModel):
    model_id: int
    job_name: str
    start_date: date
    end_date: date
    initial_capital: float = 1000000.0
    benchmark_code: str | None = None
    commission_rate: float | None = None
    stamp_tax_rate: float | None = None
    slippage_rate: float | None = None
    transfer_fee_rate: float | None = None
    execution_mode: str | None = None
    rebalance_freq: str | None = None
    holding_count: int | None = None


class BacktestCreate(BacktestBase):
    pass


class BacktestUpdate(BaseModel):
    job_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: float | None = None
    benchmark_code: str | None = None


class BacktestInDB(BacktestBase):
    id: int
    status: str
    progress: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestOut(BacktestBase):
    id: int
    status: str
    progress: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Backtest(BacktestOut):
    pass


class BacktestResultBase(BaseModel):
    backtest_id: int
    total_return: float | None = None
    annual_return: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    annual_excess_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    information_ratio: float | None = None
    turnover_rate: float | None = None
    win_rate: float | None = None
    profit_loss_ratio: float | None = None
    alpha: float | None = None
    beta: float | None = None
    metrics_json: Any | None = None


class BacktestResultCreate(BacktestResultBase):
    pass


class BacktestResultInDB(BacktestResultBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestResultOut(BacktestResultBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestResult(BacktestResultOut):
    pass


class BacktestTradeBase(BaseModel):
    backtest_id: int
    security_id: str
    action: str
    trade_date: date
    quantity: int
    price: float | None = None


class BacktestTradeCreate(BacktestTradeBase):
    pass


class BacktestTradeInDB(BacktestTradeBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestTradeOut(BacktestTradeBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestTrade(BacktestTradeOut):
    pass