"""模型注册API路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import success_response
from app.db.base import SessionLocal
from app.schemas.model_registry import ModelRegistryCreate
from app.services.model_registry_service import ModelRegistryService

router = APIRouter(prefix="/model-registry", tags=["模型注册"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
async def get_model_registry(
    model_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """查询模型列表"""
    models = ModelRegistryService.get_all_models(db, model_type=model_type, status=status)
    return success_response(
        data=[
            {
                "model_id": m.model_id,
                "model_name": m.model_name,
                "model_type": m.model_type,
                "status": m.status,
                "feature_set_version": m.feature_set_version,
                "train_start": str(m.train_start) if m.train_start else None,
                "train_end": str(m.train_end) if m.train_end else None,
            }
            for m in models
        ]
    )


@router.get("/{model_id}")
async def get_model_detail(model_id: str, db: Session = Depends(get_db)):
    """获取模型详情"""
    model = ModelRegistryService.get_model_by_id(db, model_id)
    if not model:
        return success_response(code=40401, message="模型不存在")
    return success_response(
        data={
            "model_id": model.model_id,
            "model_name": model.model_name,
            "model_type": model.model_type,
            "feature_set_version": model.feature_set_version,
            "label_version": model.label_version,
            "train_start": str(model.train_start) if model.train_start else None,
            "train_end": str(model.train_end) if model.train_end else None,
            "valid_start": str(model.valid_start) if model.valid_start else None,
            "valid_end": str(model.valid_end) if model.valid_end else None,
            "params_json": model.params_json,
            "oof_metric_json": model.oof_metric_json,
            "status": model.status,
        }
    )


@router.post("")
async def create_model(data: ModelRegistryCreate, db: Session = Depends(get_db)):
    """注册新模型"""
    model = ModelRegistryService.create_model(db, data)
    return success_response(data={"model_id": model.model_id, "status": model.status})
