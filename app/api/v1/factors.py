"""因子管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.response import success
from app.db.base import get_db
from app.models.user import User
from app.schemas.factors import (
    FactorAnalysisCreate,
    FactorCreate,
    FactorUpdate,
    FactorValueCreate,
)
from app.services.factors_service import (
    calculate_factor_values,
    create_factor,
    create_factor_analysis,
    create_factor_values,
    get_factor_analysis,
    get_factor_by_code,
    get_factor_values,
    get_factors,
    preprocess_factor_values,
    update_factor,
)

router = APIRouter()


@router.get("/")
def read_factors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    category: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取因子列表"""
    factors = get_factors(skip=skip, limit=limit, category=category, status=status, db=db)
    return success(factors)


@router.get("/{factor_id}")
def read_factor(
    factor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取因子详情"""
    factor = get_factor_by_code(str(factor_id), db=db)
    if factor is None:
        raise HTTPException(status_code=404, detail="Factor not found")
    return success(factor)


@router.post("/")
def create_factor_endpoint(
    factor: FactorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建因子"""
    result = create_factor(factor, db=db)
    return success(result)


@router.put("/{factor_id}")
def update_factor_endpoint(
    factor_id: int,
    factor_update: FactorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新因子"""
    factor = update_factor(factor_id, factor_update, db=db)
    if factor is None:
        raise HTTPException(status_code=404, detail="Factor not found")
    return success(factor)


@router.get("/{factor_id}/values")
def read_factor_values(
    factor_id: int,
    trade_date: str,
    security_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取因子值"""
    values = get_factor_values(factor_id, trade_date, security_id, db=db)
    return success(values)


@router.post("/{factor_id}/values")
def create_factor_values_endpoint(
    factor_id: int,
    trade_date: str = Query(..., description="交易日期，格式YYYYMMDD"),
    values: list[FactorValueCreate] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量创建因子值"""
    if values is None:
        values = []
    result = create_factor_values(factor_id, trade_date=trade_date, values=values, db=db)
    return success(result)


@router.post("/{factor_id}/calculate")
def calculate_factor_values_endpoint(
    factor_id: int,
    trade_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """计算因子值"""
    result = calculate_factor_values(factor_id, trade_date, [], db=db)
    return success(result)


@router.post("/{factor_id}/preprocess")
def preprocess_factor_values_endpoint(
    factor_id: int,
    trade_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """因子预处理"""
    result = preprocess_factor_values(factor_id, trade_date, db=db)
    return success(result)


@router.get("/{factor_id}/analysis")
def read_factor_analysis(
    factor_id: int,
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取因子分析结果"""
    analysis = get_factor_analysis(factor_id, start_date, end_date, db=db)
    return success(analysis)


@router.post("/{factor_id}/analysis")
def create_factor_analysis_endpoint(
    factor_id: int,
    analysis: FactorAnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建因子分析"""
    result = create_factor_analysis(factor_id, analysis, db=db)
    return success(result)
