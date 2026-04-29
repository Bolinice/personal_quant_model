"""组合相关 Pydantic 模型。"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PortfolioBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: int
    trade_date: date
    portfolio_version: int = 1
    target_exposure: float | None = None
    total_weight: float | None = None


class PortfolioCreate(PortfolioBase):
    pass


class PortfolioUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_version: int | None = None
    target_exposure: float | None = None
    total_weight: float | None = None


class PortfolioOut(PortfolioBase):
    id: int
    created_at: datetime | None = None


class PortfolioPositionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: int
    security_id: str
    weight: float
    shares: int | None = None
    target_weight: float | None = None
    actual_weight: float | None = None


class PortfolioPositionCreate(PortfolioPositionBase):
    pass


class PortfolioPositionOut(PortfolioPositionBase):
    id: int


class RebalanceRecordBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: int
    trade_date: date
    rebalance_type: str | None = None
    buy_list: Any | None = None
    sell_list: Any | None = None
    turnover: float | None = None


class RebalanceRecordCreate(RebalanceRecordBase):
    pass


class RebalanceRecordOut(RebalanceRecordBase):
    id: int


class TimingSignalBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: int
    trade_date: date
    signal_type: str | None = None
    signal_value: float | None = None
    position_ratio: float | None = None


class TimingSignalCreate(TimingSignalBase):
    pass


class TimingSignalOut(TimingSignalBase):
    id: int
