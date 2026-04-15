from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.portfolios import Portfolio, PortfolioPosition, RebalanceRecord
from app.schemas.portfolios import PortfolioCreate, PortfolioPositionCreate, RebalanceRecordCreate
import pandas as pd
import numpy as np

def get_portfolios(model_id: int, trade_date: str = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(Portfolio).filter(Portfolio.model_id == model_id)
            if trade_date:
                query = query.filter(Portfolio.trade_date == trade_date)
            return query.all()
        finally:
            db.close()
    query = db.query(Portfolio).filter(Portfolio.model_id == model_id)
    if trade_date:
        query = query.filter(Portfolio.trade_date == trade_date)
    return query.all()

def create_portfolio(portfolio: PortfolioCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_portfolio = Portfolio(**portfolio.dict())
            db.add(db_portfolio)
            db.commit()
            db.refresh(db_portfolio)
            return db_portfolio
        finally:
            db.close()
    db_portfolio = Portfolio(**portfolio.dict())
    db.add(db_portfolio)
    db.commit()
    db.refresh(db_portfolio)
    return db_portfolio

def get_portfolio_positions(portfolio_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio_id).all()
        finally:
            db.close()
    return db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio_id).all()

def create_portfolio_positions(portfolio_id: int, positions: list[PortfolioPositionCreate], db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_positions = []
            for position in positions:
                db_position = PortfolioPosition(
                    portfolio_id=portfolio_id,
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
        db_position = PortfolioPosition(
            portfolio_id=portfolio_id,
            security_id=position.security_id,
            weight=position.weight
        )
        db.add(db_position)
        db_positions.append(db_position)
    db.commit()
    for db_position in db_positions:
        db.refresh(db_position)
    return db_positions

def get_rebalance_records(model_id: int, start_date: str, end_date: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(RebalanceRecord).filter(
                RebalanceRecord.model_id == model_id,
                RebalanceRecord.trade_date >= start_date,
                RebalanceRecord.trade_date <= end_date
            ).all()
        finally:
            db.close()
    return db.query(RebalanceRecord).filter(
        RebalanceRecord.model_id == model_id,
        RebalanceRecord.trade_date >= start_date,
        RebalanceRecord.trade_date <= end_date
    ).all()

def create_rebalance_record(record: RebalanceRecordCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_record = RebalanceRecord(**record.dict())
            db.add(db_record)
            db.commit()
            db.refresh(db_record)
            return db_record
        finally:
            db.close()
    db_record = RebalanceRecord(**record.dict())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record

def generate_portfolio(model_id: int, trade_date: str, db: Session = None):
    """生成目标组合"""
    if db is None:
        db = SessionLocal()
        try:
            # 获取模型配置
            # 获取模型评分
            # 应用择时信号
            # 生成目标组合
            
            # 示例：生成一个简单的等权组合
            portfolio = PortfolioCreate(
                model_id=model_id,
                trade_date=trade_date,
                target_exposure=1.0
            )
            db_portfolio = create_portfolio(portfolio, db=db)
            
            # 示例：添加20只股票的等权持仓
            positions = []
            for i in range(1, 21):
                positions.append(PortfolioPositionCreate(
                    security_id=i,
                    weight=1.0/20
                ))
            
            create_portfolio_positions(db_portfolio.id, positions, db=db)
            
            return db_portfolio
        finally:
            db.close()
    # 获取模型配置
    # 获取模型评分
    # 应用择时信号
    # 生成目标组合
    
    # 示例：生成一个简单的等权组合
    portfolio = PortfolioCreate(
        model_id=model_id,
        trade_date=trade_date,
        target_exposure=1.0
    )
    db_portfolio = create_portfolio(portfolio, db=db)
    
    # 示例：添加20只股票的等权持仓
    positions = []
    for i in range(1, 21):
        positions.append(PortfolioPositionCreate(
            security_id=i,
            weight=1.0/20
        ))
    
    create_portfolio_positions(db_portfolio.id, positions, db=db)
    
    return db_portfolio

def generate_rebalance(model_id: int, trade_date: str, db: Session = None):
    """生成调仓记录"""
    if db is None:
        db = SessionLocal()
        try:
        # 获取当前持仓
        # 获取目标组合
        # 计算买卖清单
        # 生成调仓记录
        
        # 示例：生成一个简单的调仓记录
        rebalance = RebalanceRecordCreate(
            model_id=model_id,
            trade_date=trade_date,
            rebalance_type="scheduled",
            buy_list=[{"security_id": 21, "weight": 0.05}],
            sell_list=[{"security_id": 1, "weight": 0.05}],
            total_turnover=0.1
        )
        return create_rebalance_record(rebalance, db=db)
    finally:
        db.close()
    
    # 获取当前持仓
    # 获取目标组合
    # 计算买卖清单
    # 生成调仓记录
    
    # 示例：生成一个简单的调仓记录
    rebalance = RebalanceRecordCreate(
        model_id=model_id,
        trade_date=trade_date,
        rebalance_type="scheduled",
        buy_list=[{"security_id": 21, "weight": 0.05}],
        sell_list=[{"security_id": 1, "weight": 0.05}],
        total_turnover=0.1
    )
    return create_rebalance_record(rebalance, db=db)
