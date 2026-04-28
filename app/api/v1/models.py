"""模型管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.models.models import Model, ModelPerformance
from app.schemas.models import ModelCreate, ModelFactorWeightCreate, ModelUpdate
from app.services.models_service import (
    calculate_model_scores,
    create_model,
    create_model_factor_weights,
    get_model_factor_weights,
    get_model_scores,
    get_models,
    update_model,
    update_model_factor_weights,
)

router = APIRouter()


@router.get("/")
def read_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取模型列表"""
    models = get_models(skip=skip, limit=limit, db=db)
    return success(models)


@router.get("/{model_id}")
def read_model(model_id: int, db: Session = Depends(get_db)):
    """获取模型详情"""
    model = db.query(Model).filter(Model.id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return success(model)


@router.post("/")
def create_model_endpoint(model: ModelCreate, db: Session = Depends(get_db)):
    """创建模型"""
    result = create_model(model, db=db)
    return success(result)


@router.put("/{model_id}")
def update_model_endpoint(model_id: int, model_update: ModelUpdate, db: Session = Depends(get_db)):
    """更新模型"""
    model = update_model(model_id, model_update, db=db)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return success(model)


@router.get("/{model_id}/factor-weights")
def read_model_factor_weights(model_id: int, db: Session = Depends(get_db)):
    """获取模型因子权重"""
    weights = get_model_factor_weights(model_id, db=db)
    return success(weights)


@router.post("/{model_id}/factor-weights")
def create_model_factor_weights_endpoint(
    model_id: int, weights: list[ModelFactorWeightCreate], db: Session = Depends(get_db)
):
    """创建模型因子权重"""
    result = create_model_factor_weights(model_id, weights, db=db)
    return success(result)


@router.put("/{model_id}/factor-weights")
def update_model_factor_weights_endpoint(
    model_id: int, weights: list[ModelFactorWeightCreate], db: Session = Depends(get_db)
):
    """更新模型因子权重"""
    result = update_model_factor_weights(model_id, weights, db=db)
    return success(result)


@router.get("/{model_id}/scores")
def read_model_scores(model_id: int, trade_date: str, selected_only: bool = False, db: Session = Depends(get_db)):
    """获取模型评分"""
    scores = get_model_scores(model_id, trade_date, selected_only, db=db)
    return success(scores)


@router.post("/{model_id}/score")
def calculate_model_scores_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    """计算模型评分"""
    result = calculate_model_scores(model_id, trade_date, db=db)
    return success(result)


@router.get("/{model_id}/performance")
def read_model_performance(model_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取模型绩效"""
    perf = (
        db.query(ModelPerformance)
        .filter(ModelPerformance.model_id == model_id)
        .order_by(ModelPerformance.trade_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return success(perf)
