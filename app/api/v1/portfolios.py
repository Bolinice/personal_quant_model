from fastapi import APIRouter, Depends, HTTPException, status

from typing import List
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.services.portfolios_service import get_portfolios, create_portfolio, get_portfolio_positions, create_portfolio_positions, get_rebalance_records, create_rebalance_record, generate_portfolio, generate_rebalance
from app.models.portfolios import Portfolio, PortfolioPosition, RebalanceRecord
from app.schemas.portfolios import PortfolioCreate, PortfolioUpdate, PortfolioOut, PortfolioPositionCreate, PortfolioPositionOut, RebalanceRecordCreate, RebalanceRecordOut

router = APIRouter()

@router.get("/", response_model=List[PortfolioOut])
def read_portfolios(model_id: int, trade_date: str = None, db: Session = Depends(SessionLocal)):
    portfolios = get_portfolios(model_id, trade_date, db=db)
    return portfolios

@router.post("/", response_model=PortfolioOut)
def create_portfolio_endpoint(portfolio: PortfolioCreate, db: Session = Depends(SessionLocal)):
    return create_portfolio(portfolio, db=db)

@router.get("/{portfolio_id}/positions", response_model=List[PortfolioPositionOut])
def read_portfolio_positions(portfolio_id: int, db: Session = Depends(SessionLocal)):
    positions = get_portfolio_positions(portfolio_id, db=db)
    return positions

@router.post("/{portfolio_id}/positions", response_model=List[PortfolioPositionOut])
def create_portfolio_positions_endpoint(portfolio_id: int, positions: List[PortfolioPositionCreate], db: Session = Depends(SessionLocal)):
    return create_portfolio_positions(portfolio_id, positions, db=db)

@router.get("/rebalances", response_model=List[RebalanceRecordOut])
def read_rebalance_records(model_id: int, start_date: str, end_date: str, db: Session = Depends(SessionLocal)):
    records = get_rebalance_records(model_id, start_date, end_date, db=db)
    return records

@router.post("/generate", response_model=PortfolioOut)
def generate_portfolio_endpoint(model_id: int, trade_date: str, db: Session = Depends(SessionLocal)):
    portfolio = generate_portfolio(model_id, trade_date, db=db)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio generation failed")
    return portfolio

@router.post("/rebalance", response_model=RebalanceRecordOut)
def generate_rebalance_endpoint(model_id: int, trade_date: str, db: Session = Depends(SessionLocal)):
    record = generate_rebalance(model_id, trade_date, db=db)
    if record is None:
        raise HTTPException(status_code=404, detail="Rebalance generation failed")
    return record
