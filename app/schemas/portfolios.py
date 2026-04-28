from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PortfolioBase(BaseModel):
    portfolio_code: str
    portfolio_name: str
    description: str | None = None
    initial_capital: float = 1000000.0
    current_value: float = 1000000.0
    is_active: bool = True


class PortfolioCreate(PortfolioBase):
    pass


class PortfolioUpdate(BaseModel):
    portfolio_name: str | None = None
    description: str | None = None
    initial_capital: float | None = None
    current_value: float | None = None
    is_active: bool | None = None


class PortfolioInDB(PortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioOut(PortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Portfolio(PortfolioOut):
    pass


class PortfolioPositionBase(BaseModel):
    portfolio_id: int
    security_id: int
    quantity: float
    weight: float


class PortfolioPositionCreate(PortfolioPositionBase):
    pass


class PortfolioPositionInDB(PortfolioPositionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioPositionOut(PortfolioPositionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioPosition(PortfolioPositionOut):
    pass


class RebalanceRecordBase(BaseModel):
    model_id: int
    trade_date: datetime
    rebalance_type: str  # scheduled, signal, risk
    buy_list: list = []
    sell_list: list = []
    total_turnover: float = 0.0


class RebalanceRecordCreate(RebalanceRecordBase):
    pass


class RebalanceRecordInDB(RebalanceRecordBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RebalanceRecordOut(RebalanceRecordBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RebalanceRecord(RebalanceRecordOut):
    pass
