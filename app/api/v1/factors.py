"""因子管理 API。"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.factors_service import (
    get_factors, get_factor_by_code, create_factor, update_factor,
    get_factor_values, create_factor_values, get_factor_analysis,
    create_factor_analysis, calculate_factor_values, preprocess_factor_values,
)
from app.schemas.factors import (
    FactorCreate, FactorUpdate, FactorValueCreate, FactorAnalysisCreate,
    FactorOut, FactorValueOut, FactorAnalysisOut,
)
from app.core.response import success, error

router = APIRouter()


@router.get("/")
def read_factors(skip: int = 0, limit: int = 100, category: str = None, status: str = None, db: Session = Depends(get_db)):
    """获取因子列表"""
    factors = get_factors(skip=skip, limit=limit, category=category, status=status, db=db)
    return success(factors)


@router.get("/{factor_id}")
def read_factor(factor_id: int, db: Session = Depends(get_db)):
    """获取因子详情"""
    factor = get_factor_by_code(str(factor_id), db=db)
    if factor is None:
        raise HTTPException(status_code=404, detail="Factor not found")
    return success(factor)


@router.post("/")
def create_factor_endpoint(factor: FactorCreate, db: Session = Depends(get_db)):
    """创建因子"""
    result = create_factor(factor, db=db)
    return success(result)


@router.put("/{factor_id}")
def update_factor_endpoint(factor_id: int, factor_update: FactorUpdate, db: Session = Depends(get_db)):
    """更新因子"""
    factor = update_factor(factor_id, factor_update, db=db)
    if factor is None:
        raise HTTPException(status_code=404, detail="Factor not found")
    return success(factor)


@router.get("/{factor_id}/values")
def read_factor_values(factor_id: int, trade_date: str, security_id: int = None, db: Session = Depends(get_db)):
    """获取因子值"""
    values = get_factor_values(factor_id, trade_date, security_id, db=db)
    return success(values)


@router.post("/{factor_id}/values")
def create_factor_values_endpoint(factor_id: int, values: List[FactorValueCreate], db: Session = Depends(get_db)):
    """批量创建因子值"""
    result = create_factor_values(factor_id, trade_date="", values=values, db=db)
    return success(result)


@router.post("/{factor_id}/calculate")
def calculate_factor_values_endpoint(factor_id: int, trade_date: str, db: Session = Depends(get_db)):
    """计算因子值"""
    result = calculate_factor_values(factor_id, trade_date, [], db=db)
    return success(result)


@router.post("/{factor_id}/preprocess")
def preprocess_factor_values_endpoint(factor_id: int, trade_date: str, db: Session = Depends(get_db)):
    """因子预处理"""
    result = preprocess_factor_values(factor_id, trade_date, db=db)
    return success(result)


@router.get("/{factor_id}/analysis")
def read_factor_analysis(factor_id: int, start_date: str, end_date: str, db: Session = Depends(get_db)):
    """获取因子分析结果"""
    analysis = get_factor_analysis(factor_id, start_date, end_date, db=db)
    return success(analysis)


@router.post("/{factor_id}/analysis")
def create_factor_analysis_endpoint(factor_id: int, analysis: FactorAnalysisCreate, db: Session = Depends(get_db)):
    """创建因子分析"""
    result = create_factor_analysis(factor_id, analysis, db=db)
    return success(result)
