from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

class SimulatedPortfolioBase(BaseModel):
    portfolio_code: str
    portfolio_name: str
    description: Optional[str] = None
    initial_capital: float = 1000000.0
    current_value: float = 1000000.0

class SimulatedPortfolioCreate(SimulatedPortfolioBase):
    pass

class SimulatedPortfolioUpdate(BaseModel):
    portfolio_name: Optional[str] = None
    description: Optional[str] = None
    initial_capital: Optional[float] = None
    current_value: Optional[float] = None

class SimulatedPortfolioInDB(SimulatedPortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SimulatedPortfolioOut(SimulatedPortfolioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SimulatedPortfolio(SimulatedPortfolioOut):
    pass

class SimulatedPortfolioPositionBase(BaseModel):
    portfolio_id: int
    security_id: int
    quantity: float
    weight: float

class SimulatedPortfolioPositionCreate(SimulatedPortfolioPositionBase):
    pass

class SimulatedPortfolioPositionInDB(SimulatedPortfolioPositionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SimulatedPortfolioPositionOut(SimulatedPortfolioPositionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SimulatedPortfolioPosition(SimulatedPortfolioPositionOut):
    pass

class SimulatedPortfolioNavBase(BaseModel):
    portfolio_id: int
    trade_date: datetime
    nav: float
    daily_return: float
    cumulative_return: float

class SimulatedPortfolioNavCreate(SimulatedPortfolioNavBase):
    pass

class SimulatedPortfolioNavInDB(SimulatedPortfolioNavBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SimulatedPortfolioNavOut(SimulatedPortfolioNavBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SimulatedPortfolioNav(SimulatedPortfolioNavOut):
    pass