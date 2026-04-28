from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BacktestBase(BaseModel):
    name: str
    description: str | None = None
    start_date: datetime
    end_date: datetime
    initial_capital: float = 1000000.0


class BacktestCreate(BacktestBase):
    pass


class BacktestUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    initial_capital: float | None = None


class BacktestInDB(BacktestBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestOut(BacktestBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Backtest(BacktestOut):
    pass


class BacktestResultBase(BaseModel):
    backtest_id: int
    trade_date: datetime
    total_return: float
    benchmark_return: float
    excess_return: float
    sharpe_ratio: float


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
    security_id: int
    trade_type: str  # buy, sell
    trade_date: datetime
    quantity: float
    price: float


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
