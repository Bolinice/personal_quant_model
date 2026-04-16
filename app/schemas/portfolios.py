from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

class PortfolioBase(BaseModel):
    portfolio_code: str
    portfolio_name: str
    description: Optional[str] = None
    initial_capital: float = 1000000.0
    current_value: float = 1000000.0
    is_active: bool = True

class PortfolioCreate(PortfolioBase):
    pass

class PortfolioUpdate(BaseModel):
    portfolio_name: Optional[str] = None
    description: Optional[str] = None
    initial_capital: Optional[float] = None
    current_value: Optional[float] = None
    is_active: Optional[bool] = None

class PortfolioInDB(PortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PortfolioOut(PortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

class PortfolioPositionOut(PortfolioPositionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PortfolioPosition(PortfolioPositionOut):
    pass