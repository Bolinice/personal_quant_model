from typing import List
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.models import Model, ModelFactorWeight, ModelScore
from app.schemas.models import ModelCreate, ModelUpdate, ModelFactorWeightCreate, ModelScoreCreate
import pandas as pd
import numpy as np

def get_factor_values(factor_id: int, trade_date: str, db: Session):
    """导入get_factor_values函数"""
    from app.services.factors_service import get_factor_values as gfvs
    return gfvs(factor_id, trade_date, db=None if db is None else db)

def get_models(skip: int = 0, limit: int = 100, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(Model).offset(skip).limit(limit).all()
        finally:
            db.close()
    return db.query(Model).offset(skip).limit(limit).all()

def get_model_by_code(model_code: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(Model).filter(Model.model_code == model_code).first()
        finally:
            db.close()
    return db.query(Model).filter(Model.model_code == model_code).first()

def create_model(model: ModelCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_model = Model(**model.dict())
            db.add(db_model)
            db.commit()
            db.refresh(db_model)
            return db_model
        finally:
            db.close()
    db_model = Model(**model.dict())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model

def update_model(model_id: int, model_update: ModelUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_model = db.query(Model).filter(Model.id == model_id).first()
            if not db_model:
                return None
            update_data = model_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_model, key, value)
            db.commit()
            db.refresh(db_model)
            return db_model
        finally:
            db.close()
    db_model = db.query(Model).filter(Model.id == model_id).first()
    if not db_model:
        return None
    update_data = model_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_model, key, value)
    db.commit()
    db.refresh(db_model)
    return db_model

def get_model_factor_weights(model_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(ModelFactorWeight).filter(ModelFactorWeight.model_id == model_id).all()
        finally:
            db.close()
    return db.query(ModelFactorWeight).filter(ModelFactorWeight.model_id == model_id).all()

def create_model_factor_weights(model_id: int, weights: List[ModelFactorWeightCreate], db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_weights = []
            for weight in weights:
                db_weight = ModelFactorWeight(
                    model_id=model_id,
                    factor_id=weight.factor_id,
                    weight=weight.weight
                )
                db.add(db_weight)
                db_weights.append(db_weight)
            db.commit()
            for db_weight in db_weights:
                db.refresh(db_weight)
            return db_weights
        finally:
            db.close()
    db_weights = []
    for weight in weights:
        db_weight = ModelFactorWeight(
            model_id=model_id,
            factor_id=weight.factor_id,
            weight=weight.weight
        )
        db.add(db_weight)
        db_weights.append(db_weight)
    db.commit()
    for db_weight in db_weights:
        db.refresh(db_weight)
    return db_weights

def update_model_factor_weights(model_id: int, weights: List[ModelFactorWeightCreate], db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            # 删除旧权重
            db.query(ModelFactorWeight).filter(ModelFactorWeight.model_id == model_id).delete()
            db.commit()
            
            # 添加新权重
            return create_model_factor_weights(model_id, weights, db=db)
        finally:
            db.close()
    # 删除旧权重
    db.query(ModelFactorWeight).filter(ModelFactorWeight.model_id == model_id).delete()
    db.commit()
    
    # 添加新权重
    return create_model_factor_weights(model_id, weights, db=db)

def get_model_scores(model_id: int, trade_date: str, selected_only: bool = False, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(ModelScore).filter(ModelScore.model_id == model_id, ModelScore.trade_date == trade_date)
            if selected_only:
                # 这里应该根据模型配置获取选中的股票
                pass
            return query.all()
        finally:
            db.close()
    query = db.query(ModelScore).filter(ModelScore.model_id == model_id, ModelScore.trade_date == trade_date)
    if selected_only:
        pass
    return query.all()

def create_model_scores(model_id: int, trade_date: str, scores: list, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_scores = []
            for score in scores:
                db_score = ModelScore(
                    model_id=model_id,
                    trade_date=trade_date,
                    security_id=score['security_id'],
                    total_score=score['total_score']
                )
                db.add(db_score)
                db_scores.append(db_score)
            db.commit()
            for db_score in db_scores:
                db.refresh(db_score)
            return db_scores
        finally:
            db.close()
    db_scores = []
    for score in scores:
        db_score = ModelScore(
            model_id=model_id,
            trade_date=trade_date,
            security_id=score['security_id'],
            total_score=score['total_score']
        )
        db.add(db_score)
        db_scores.append(db_score)
    db.commit()
    for db_score in db_scores:
        db.refresh(db_score)
    return db_scores

def calculate_model_scores(model_id: int, trade_date: str, db: Session = None):
    """计算模型评分"""
    if db is None:
        db = SessionLocal()
        try:
            # 获取模型配置
            model = get_model_by_code(str(model_id), db=db)
            if not model:
                return []
            
            # 获取因子权重
            weights = get_model_factor_weights(model_id, db=db)
            if not weights:
                return []
            
            # 获取因子值
            factor_values = {}
            for weight in weights:
                factor_values[weight.factor_id] = get_factor_values(weight.factor_id, trade_date, db=db)
            
            # 计算总分（简化示例）
            scores = []
            for security_id in range(1, 101):  # 模拟100只股票
                total_score = 0
                for weight in weights:
                    # 获取该股票的因子值
                    factor_value = next((fv.value for fv in factor_values[weight.factor_id] if fv.security_id == security_id), 0)
                    total_score += factor_value * weight.weight
                
                scores.append({
                    'security_id': security_id,
                    'total_score': total_score
                })
            
            # 保存评分
            return create_model_scores(model_id, trade_date, scores, db=db)
        finally:
            db.close()
    # 获取模型配置
    model = get_model_by_code(str(model_id), db=db)
    if not model:
        return []
    
    # 获取因子权重
    weights = get_model_factor_weights(model_id, db=db)
    if not weights:
        return []
    
    # 获取因子值
    factor_values = {}
    for weight in weights:
        factor_values[weight.factor_id] = get_factor_values(weight.factor_id, trade_date, db=db)
    
    # 计算总分（简化示例）
    scores = []
    for security_id in range(1, 101):  # 模拟100只股票
        total_score = 0
        for weight in weights:
            # 获取该股票的因子值
            factor_value = next((fv.value for fv in factor_values[weight.factor_id] if fv.security_id == security_id), 0)
            total_score += factor_value * weight.weight
        
        scores.append({
            'security_id': security_id,
            'total_score': total_score
        })
    
    # 保存评分
    return create_model_scores(model_id, trade_date, scores, db=db)
