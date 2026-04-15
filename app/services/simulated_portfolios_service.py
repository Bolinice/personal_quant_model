from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.simulated_portfolios import SimulatedPortfolio, SimulatedPortfolioPosition, SimulatedPortfolioNav
from app.schemas.simulated_portfolios import SimulatedPortfolioCreate, SimulatedPortfolioPositionCreate, SimulatedPortfolioNavCreate
import pandas as pd
import numpy as np

def get_simulated_portfolios(model_id: int = None, skip: int = 0, limit: int = 100, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(SimulatedPortfolio)
            if model_id:
                query = query.filter(SimulatedPortfolio.model_id == model_id)
            return query.offset(skip).limit(limit).all()
        finally:
            db.close()
    query = db.query(SimulatedPortfolio)
    if model_id:
        query = query.filter(SimulatedPortfolio.model_id == model_id)
    return query.offset(skip).limit(limit).all()

def create_simulated_portfolio(portfolio: SimulatedPortfolioCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_portfolio = SimulatedPortfolio(**portfolio.dict())
            db.add(db_portfolio)
            db.commit()
            db.refresh(db_portfolio)
            return db_portfolio
        finally:
            db.close()
    db_portfolio = SimulatedPortfolio(**portfolio.dict())
    db.add(db_portfolio)
    db.commit()
    db.refresh(db_portfolio)
    return db_portfolio

def get_simulated_portfolio_positions(portfolio_id: int, trade_date: str = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(SimulatedPortfolioPosition).filter(SimulatedPortfolioPosition.portfolio_id == portfolio_id)
            if trade_date:
                query = query.filter(SimulatedPortfolioPosition.trade_date == trade_date)
            return query.all()
        finally:
            db.close()
    query = db.query(SimulatedPortfolioPosition).filter(SimulatedPortfolioPosition.portfolio_id == portfolio_id)
    if trade_date:
        query = query.filter(SimulatedPortfolioPosition.trade_date == trade_date)
    return query.all()

def create_simulated_portfolio_positions(portfolio_id: int, positions: list[SimulatedPortfolioPositionCreate], db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_positions = []
            for position in positions:
                db_position = SimulatedPortfolioPosition(
                    portfolio_id=portfolio_id,
                    trade_date=position.trade_date,
                    security_id=position.security_id,
                    weight=position.weight
                )
                db.add(db_position)
                db_positions.append(db_position)
            db.commit()
            for db_position in db_positions:
                db.refresh(db_position)
            return db_positions
        finally:
            db.close()
    db_positions = []
    for position in positions:
        db_position = SimulatedPortfolioPosition(
            portfolio_id=portfolio_id,
            trade_date=position.trade_date,
            security_id=position.security_id,
            weight=position.weight
        )
        db.add(db_position)
        db_positions.append(db_position)
    db.commit()
    for db_position in db_positions:
        db.refresh(db_position)
    return db_positions

def get_simulated_portfolio_navs(portfolio_id: int, start_date: str = None, end_date: str = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(SimulatedPortfolioNav).filter(SimulatedPortfolioNav.portfolio_id == portfolio_id)
            if start_date:
                query = query.filter(SimulatedPortfolioNav.trade_date >= start_date)
            if end_date:
                query = query.filter(SimulatedPortfolioNav.trade_date <= end_date)
            return query.all()
        finally:
            db.close()
    query = db.query(SimulatedPortfolioNav).filter(SimulatedPortfolioNav.portfolio_id == portfolio_id)
    if start_date:
        query = query.filter(SimulatedPortfolioNav.trade_date >= start_date)
    if end_date:
        query = query.filter(SimulatedPortfolioNav.trade_date <= end_date)
    return query.all()

def create_simulated_portfolio_nav(portfolio_id: int, nav: SimulatedPortfolioNavCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_nav = SimulatedPortfolioNav(**nav.dict())
            db.add(db_nav)
            db.commit()
            db.refresh(db_nav)
            return db_nav
        finally:
            db.close()
    db_nav = SimulatedPortfolioNav(**nav.dict())
    db.add(db_nav)
    db.commit()
    db.refresh(db_nav)
    return db_nav

def update_simulated_portfolio(portfolio_id: int, portfolio_update: dict, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_portfolio = db.query(SimulatedPortfolio).filter(SimulatedPortfolio.id == portfolio_id).first()
            if not db_portfolio:
                return None
            for key, value in portfolio_update.items():
                setattr(db_portfolio, key, value)
            db.commit()
            db.refresh(db_portfolio)
            return db_portfolio
        finally:
            db.close()
    db_portfolio = db.query(SimulatedPortfolio).filter(SimulatedPortfolio.id == portfolio_id).first()
    if not db_portfolio:
        return None
    for key, value in portfolio_update.items():
        setattr(db_portfolio, key, value)
    db.commit()
    db.refresh(db_portfolio)
    return db_portfolio

def calculate_simulated_portfolio_nav(portfolio_id: int, trade_date: str, db: Session = None):
    """计算模拟组合净值"""
    if db is None:
        db = SessionLocal()
        try:
            # 获取组合信息
            portfolio = db.query(SimulatedPortfolio).filter(SimulatedPortfolio.id == portfolio_id).first()
            if not portfolio:
                return None
            
            # 获取当前持仓
            positions = get_simulated_portfolio_positions(portfolio_id, trade_date, db=db)
            if not positions:
                return None
            
            # 获取行情数据计算净值（简化示例）
            # 这里应该根据持仓和行情数据计算净值
            nav = portfolio.initial_capital * (1 + np.random.normal(0, 0.01))  # 模拟净值变化
            
            # 创建净值记录
            nav_record = SimulatedPortfolioNavCreate(
                portfolio_id=portfolio_id,
                trade_date=trade_date,
                nav=nav
            )
            
            return create_simulated_portfolio_nav(portfolio_id, nav_record, db=db)
        finally:
            db.close()
    # 获取组合信息
    portfolio = db.query(SimulatedPortfolio).filter(SimulatedPortfolio.id == portfolio_id).first()
    if not portfolio:
        return None
    
    # 获取当前持仓
    positions = get_simulated_portfolio_positions(portfolio_id, trade_date, db=db)
    if not positions:
        return None
    
    # 获取行情数据计算净值（简化示例）
    nav = portfolio.initial_capital * (1 + np.random.normal(0, 0.01))  # 模拟净值变化
    
    # 创建净值记录
    nav_record = SimulatedPortfolioNavCreate(
        portfolio_id=portfolio_id,
        trade_date=trade_date,
        nav=nav
    )
    
    return create_simulated_portfolio_nav(portfolio_id, nav_record, db=db)
