from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.services.factors_service import get_factors, get_factor_by_code, create_factor, update_factor, get_factor_values, create_factor_values, get_factor_analysis, create_factor_analysis, calculate_factor_values, preprocess_factor_values
from app.models.factors import Factor, FactorValue, FactorAnalysis
from app.schemas.factors import FactorCreate, FactorUpdate, FactorValueCreate, FactorAnalysisCreate, FactorOut, FactorValueOut, FactorAnalysisOut

router = APIRouter()

@router.get("/", response_model=list[FactorOut])
def read_factors(skip: int = 0, limit: int = 100, category: str = None, status: str = None, db: Session = Depends(SessionLocal)):
    factors = get_factors(skip=skip, limit=limit, category=category, status=status, db=db)
    return factors

@router.get("/{factor_id}", response_model=FactorOut)
def read_factor(factor_id: int, db: Session = Depends(SessionLocal)):
    factor = get_factor_by_code(str(factor_id), db=db)
    if factor is None:
        raise HTTPException(status_code=404, detail="Factor not found")
    return factor

@router.post("/", response_model=FactorOut)
def create_factor_endpoint(factor: FactorCreate, db: Session = Depends(SessionLocal)):
    return create_factor(factor, db=db)

@router.put("/{factor_id}", response_model=FactorOut)
def update_factor_endpoint(factor_id: int, factor_update: FactorUpdate, db: Session = Depends(SessionLocal)):
    factor = update_factor(factor_id, factor_update, db=db)
    if factor is None:
        raise HTTPException(status_code=404, detail="Factor not found")
    return factor

@router.get("/{factor_id}/values", response_model=list[FactorValueOut])
def read_factor_values(factor_id: int, trade_date: str, security_id: int = None, db: Session = Depends(SessionLocal)):
    values = get_factor_values(factor_id, trade_date, security_id, db=db)
    return values

@router.post("/{factor_id}/values", response_model=list[FactorValueOut])
def create_factor_values_endpoint(factor_id: int, values: list[FactorValueCreate], db: Session = Depends(SessionLocal)):
    return create_factor_values(factor_id, values, db=db)

@router.post("/{factor_id}/calculate", response_model=list[FactorValueOut])
def calculate_factor_values_endpoint(factor_id: int, trade_date: str, db: Session = Depends(SessionLocal)):
    # 这里应该获取相关证券列表
    # 示例：模拟计算
    return calculate_factor_values(factor_id, trade_date, [], db=db)

@router.post("/{factor_id}/preprocess", response_model=list[FactorValueOut])
def preprocess_factor_values_endpoint(factor_id: int, trade_date: str, db: Session = Depends(SessionLocal)):
    return preprocess_factor_values(factor_id, trade_date, db=db)

@router.get("/{factor_id}/analysis", response_model=list[FactorAnalysisOut])
def read_factor_analysis(factor_id: int, start_date: str, end_date: str, db: Session = Depends(SessionLocal)):
    analysis = get_factor_analysis(factor_id, start_date, end_date, db=db)
    return analysis

@router.post("/{factor_id}/analysis", response_model=FactorAnalysisOut)
def create_factor_analysis_endpoint(factor_id: int, analysis: FactorAnalysisCreate, db: Session = Depends(SessionLocal)):
    return create_factor_analysis(factor_id, analysis, db=db)

@router.post("/{factor_id}/ic-analysis", response_model=FactorAnalysisOut)
def calculate_ic_analysis_endpoint(factor_id: int, start_date: str, end_date: str, db: Session = Depends(SessionLocal)):
    analysis = calculate_ic_analysis(factor_id, start_date, end_date, db=db)
    if analysis is None:
        raise HTTPException(status_code=404, detail="IC analysis failed")
    return analysis

@router.post("/{factor_id}/group-returns", response_model=FactorAnalysisOut)
def calculate_group_returns_endpoint(factor_id: int, start_date: str, end_date: str, db: Session = Depends(SessionLocal)):
    analysis = calculate_group_returns(factor_id, start_date, end_date, db=db)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Group returns analysis failed")
    return analysis

@router.post("/{factor_id}/correlation/{compare_factor_id}", response_model=FactorAnalysisOut)
def calculate_factor_correlation_endpoint(factor_id: int, compare_factor_id: int, start_date: str, end_date: str, db: Session = Depends(SessionLocal)):
    analysis = calculate_factor_correlation(factor_id, compare_factor_id, start_date, end_date, db=db)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Correlation analysis failed")
    return analysis
