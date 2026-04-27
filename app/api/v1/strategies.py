"""
策略管理API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.base import get_db
from app.models.models import Model, ModelFactorWeight
from app.core.response import success, error, page_result
from app.api.v1.auth import get_current_user
from app.models.user import User


router = APIRouter()


class StrategyCreate(BaseModel):
    model_name: str
    model_type: str = "scoring"
    description: Optional[str] = None
    factor_ids: List[int] = []
    factor_weights: dict = {}
    config: dict = {}


class StrategyUpdate(BaseModel):
    model_name: Optional[str] = None
    description: Optional[str] = None
    factor_ids: Optional[List[int]] = None
    factor_weights: Optional[dict] = None
    config: Optional[dict] = None
    status: Optional[str] = None


@router.get("/")
def list_strategies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取策略列表"""
    query = db.query(Model)
    if status:
        query = query.filter(Model.status == status)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_result(
        items=[{
            "id": m.id,
            "model_code": m.model_code,
            "model_name": m.model_name,
            "model_type": m.model_type,
            "status": m.status,
            "version": m.version,
            "created_at": str(m.created_at),
        } for m in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取策略详情"""
    model = db.query(Model).filter(Model.id == strategy_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="策略不存在")

    # 获取因子权重
    weights = db.query(ModelFactorWeight).filter(
        ModelFactorWeight.model_id == strategy_id,
    ).all()

    return success({
        "id": model.id,
        "model_code": model.model_code,
        "model_name": model.model_name,
        "model_type": model.model_type,
        "description": model.description,
        "version": model.version,
        "status": model.status,
        "factor_ids": model.factor_ids,
        "factor_weights": model.factor_weights,
        "model_config": model.model_config,
        "ic_mean": model.ic_mean,
        "ic_ir": model.ic_ir,
        "created_at": str(model.created_at),
        "updated_at": str(model.updated_at) if model.updated_at else None,
    })


@router.post("/")
def create_strategy(
    strategy: StrategyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建策略"""
    import uuid
    model = Model(
        model_code=f"STR_{uuid.uuid4().hex[:8].upper()}",
        model_name=strategy.model_name,
        model_type=strategy.model_type,
        description=strategy.description,
        factor_ids=strategy.factor_ids,
        factor_weights=strategy.factor_weights,
        model_config=strategy.config,
        status="draft",
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    # 保存因子权重
    for factor_id, weight in strategy.factor_weights.items():
        fw = ModelFactorWeight(
            model_id=model.id,
            factor_id=int(factor_id),
            weight=float(weight),
        )
        db.add(fw)
    db.commit()

    return success({"id": model.id, "model_code": model.model_code}, message="策略创建成功")


# 映射 Pydantic 字段名到 ORM 模型字段名
_FIELD_MAP = {"config": "model_config"}


@router.put("/{strategy_id}")
def update_strategy(
    strategy_id: int,
    strategy: StrategyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新策略"""
    model = db.query(Model).filter(Model.id == strategy_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="策略不存在")

    update_data = strategy.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        orm_key = _FIELD_MAP.get(key, key)
        setattr(model, orm_key, value)

    db.commit()
    return success(message="策略更新成功")


@router.post("/{strategy_id}/publish")
def publish_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发布策略"""
    model = db.query(Model).filter(Model.id == strategy_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="策略不存在")

    if model.status == "active":
        raise HTTPException(status_code=400, detail="策略已发布")

    model.status = "active"
    db.commit()
    return success(message="策略发布成功")


@router.post("/{strategy_id}/archive")
def archive_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """归档策略"""
    model = db.query(Model).filter(Model.id == strategy_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="策略不存在")

    model.status = "archived"
    db.commit()
    return success(message="策略已归档")
