"""因子管理 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.response import success
from app.db.base import get_db
from app.models.user import User
from app.schemas.factors import (
    FactorAnalysisCreate,
    FactorCalculationRequest,
    FactorCalculationResponse,
    FactorCreate,
    FactorGroupResponse,
    FactorListResponse,
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
    values: list[FactorValueCreate] | None = None,
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


@router.get("/groups", response_model=list[FactorGroupResponse])
async def get_factor_groups(db: Session = Depends(get_db)):
    """获取所有因子组"""
    from app.core.factor_calculator import FACTOR_GROUPS

    groups = []
    for group_key, factors in FACTOR_GROUPS.items():
        group_name_map = {
            "valuation": "估值因子",
            "growth": "成长因子",
            "quality": "质量因子",
            "momentum": "动量因子",
            "volatility": "波动率因子",
            "liquidity": "流动性因子",
            "northbound": "北向资金因子",
            "analyst": "分析师因子",
            "earnings_quality": "盈利质量因子",
            "risk_penalty": "风险惩罚因子",
            "smart_money": "聪明钱因子",
            "technical": "技术因子",
        }
        groups.append(
            FactorGroupResponse(
                group_key=group_key,
                group_name=group_name_map.get(group_key, group_key),
                factors=factors,
                factor_count=len(factors),
            )
        )
    return groups


@router.get("/list", response_model=FactorListResponse)
async def list_all_factors(db: Session = Depends(get_db)):
    """列出所有可计算的因子"""
    from app.core.factor_calculator import FACTOR_DIRECTIONS, FACTOR_GROUPS

    all_factors = []
    for group_key, factors in FACTOR_GROUPS.items():
        for factor_code in factors:
            all_factors.append(
                {
                    "factor_code": factor_code,
                    "group": group_key,
                    "direction": FACTOR_DIRECTIONS.get(factor_code, 1),
                }
            )

    return FactorListResponse(
        total_factors=len(all_factors),
        total_groups=len(FACTOR_GROUPS),
        factors=all_factors,
    )


@router.post("/calculate", response_model=FactorCalculationResponse)
async def calculate_factors(
    request: FactorCalculationRequest, db: Session = Depends(get_db)
):
    """批量计算因子"""
    from datetime import datetime

    from app.core.factor_calculator import FactorCalculator

    # 转换日期格式
    if isinstance(request.trade_date, str):
        trade_date = datetime.strptime(request.trade_date, "%Y-%m-%d").date()
    else:
        trade_date = request.trade_date

    # 初始化因子计算器
    calculator = FactorCalculator(db)

    # 计算因子
    if request.factor_groups:
        # 计算指定组的因子
        results = []
        for ts_code in request.ts_codes:
            stock_factors = {}
            for group in request.factor_groups:
                group_method = f"calc_{group}_factors"
                if hasattr(calculator, group_method):
                    method = getattr(calculator, group_method)
                    factors = method(ts_code, trade_date, request.lookback_days)
                    stock_factors.update(factors)
            results.append({"ts_code": ts_code, "trade_date": str(trade_date), **stock_factors})
    else:
        # 计算所有因子
        results = []
        for ts_code in request.ts_codes:
            factors = calculator.calc_all_factors(ts_code, trade_date, request.lookback_days)
            results.append({"ts_code": ts_code, "trade_date": str(trade_date), **factors})

    # 统计因子数量
    total_factors = len(results[0]) - 2 if results else 0  # 减去 ts_code 和 trade_date

    return FactorCalculationResponse(
        success=True,
        message=f"Successfully calculated factors for {len(results)} stocks",
        data=results,
        total_stocks=len(results),
        total_factors=total_factors,
    )
