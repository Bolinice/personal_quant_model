from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import date

class PortfolioBase(BaseModel):
    model_id: int
    trade_date: date
    target_exposure: float = 1.0

class PortfolioCreate(PortfolioBase):
    pass

class PortfolioInDB(PortfolioBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class PortfolioOut(PortfolioBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class PortfolioPositionBase(BaseModel):
    portfolio_id: int
    security_id: int
    weight: float

class PortfolioPositionCreate(PortfolioPositionBase):
    pass

class PortfolioPositionInDB(PortfolioPositionBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class PortfolioPositionOut(PortfolioPositionBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class RebalanceRecordBase(BaseModel):
    model_id: int
    trade_date: date
    rebalance_type: str = "scheduled"
    buy_list: Optional[List[Dict[str, Any]]] = None
    sell_list: Optional[List[Dict[str, Any]]] = None
    total_turnover: float = 0.0

class RebalanceRecordCreate(RebalanceRecordBase):
    pass

class RebalanceRecordInDB(RebalanceRecordBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class RebalanceRecordOut(RebalanceRecordBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
