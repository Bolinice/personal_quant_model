from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import date

class SimulatedPortfolioBase(BaseModel):
    model_id: int
    name: str
    benchmark_code: str
    start_date: date
    initial_capital: float = 1000000.0

class SimulatedPortfolioCreate(SimulatedPortfolioBase):
    pass

class SimulatedPortfolioUpdate(BaseModel):
    name: Optional[str] = None
    benchmark_code: Optional[str] = None
    initial_capital: Optional[float] = None

class SimulatedPortfolioInDB(SimulatedPortfolioBase):
    id: int
    current_value: float
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class SimulatedPortfolioOut(SimulatedPortfolioBase):
    id: int
    current_value: float
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class SimulatedPortfolioPositionBase(BaseModel):
    portfolio_id: int
    trade_date: date
    security_id: int
    weight: float

class SimulatedPortfolioPositionCreate(SimulatedPortfolioPositionBase):
    pass

class SimulatedPortfolioPositionInDB(SimulatedPortfolioPositionBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class SimulatedPortfolioPositionOut(SimulatedPortfolioPositionBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class SimulatedPortfolioNavBase(BaseModel):
    portfolio_id: int
    trade_date: date
    nav: float

class SimulatedPortfolioNavCreate(SimulatedPortfolioNavBase):
    pass

class SimulatedPortfolioNavInDB(SimulatedPortfolioNavBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class SimulatedPortfolioNavOut(SimulatedPortfolioNavBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
