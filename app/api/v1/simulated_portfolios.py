from fastapi import APIRouter, Depends, HTTPException, status

from typing import List
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.simulated_portfolios_service import get_simulated_portfolios, create_simulated_portfolio, get_simulated_portfolio_positions, create_simulated_portfolio_positions, get_simulated_portfolio_navs, create_simulated_portfolio_nav, update_simulated_portfolio, calculate_simulated_portfolio_nav
from app.models.simulated_portfolios import SimulatedPortfolio, SimulatedPortfolioPosition, SimulatedPortfolioNav
from app.schemas.simulated_portfolios import SimulatedPortfolioCreate, SimulatedPortfolioPositionCreate, SimulatedPortfolioNavCreate, SimulatedPortfolioOut, SimulatedPortfolioPositionOut, SimulatedPortfolioNavOut

router = APIRouter()

@router.get("/", response_model=List[SimulatedPortfolioOut])
def read_simulated_portfolios(model_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    portfolios = get_simulated_portfolios(model_id=model_id, skip=skip, limit=limit, db=db)
    return portfolios

@router.post("/", response_model=SimulatedPortfolioOut)
def create_simulated_portfolio_endpoint(portfolio: SimulatedPortfolioCreate, db: Session = Depends(get_db)):
    return create_simulated_portfolio(portfolio, db=db)

@router.get("/{portfolio_id}/positions", response_model=List[SimulatedPortfolioPositionOut])
def read_simulated_portfolio_positions(portfolio_id: int, trade_date: str = None, db: Session = Depends(get_db)):
    positions = get_simulated_portfolio_positions(portfolio_id, trade_date, db=db)
    return positions

@router.post("/{portfolio_id}/positions", response_model=List[SimulatedPortfolioPositionOut])
def create_simulated_portfolio_positions_endpoint(portfolio_id: int, positions: List[SimulatedPortfolioPositionCreate], db: Session = Depends(get_db)):
    return create_simulated_portfolio_positions(portfolio_id, positions, db=db)

@router.get("/{portfolio_id}/navs", response_model=List[SimulatedPortfolioNavOut])
def read_simulated_portfolio_navs(portfolio_id: int, start_date: str = None, end_date: str = None, db: Session = Depends(get_db)):
    navs = get_simulated_portfolio_navs(portfolio_id, start_date, end_date, db=db)
    return navs

@router.post("/{portfolio_id}/nav", response_model=SimulatedPortfolioNavOut)
def calculate_simulated_portfolio_nav_endpoint(portfolio_id: int, trade_date: str, db: Session = Depends(get_db)):
    nav = calculate_simulated_portfolio_nav(portfolio_id, trade_date, db=db)
    if nav is None:
        raise HTTPException(status_code=404, detail="NAV calculation failed")
    return nav

@router.put("/{portfolio_id}", response_model=SimulatedPortfolioOut)
def update_simulated_portfolio_endpoint(portfolio_id: int, updates: dict, db: Session = Depends(get_db)):
    portfolio = update_simulated_portfolio(portfolio_id, updates, db=db)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Simulated portfolio not found")
    return portfolio
