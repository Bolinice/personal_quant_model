"""模型注册服务"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.model_registry import ModelRegistry
from app.schemas.model_registry import ModelRegistryCreate


class ModelRegistryService:
    """模型注册服务"""

    @staticmethod
    def get_all_models(
        db: Session,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
    ) -> List[ModelRegistry]:
        """获取模型列表"""
        query = db.query(ModelRegistry)
        if status:
            query = query.filter(ModelRegistry.status == status)
        if model_type:
            query = query.filter(ModelRegistry.model_type == model_type)
        return query.order_by(ModelRegistry.created_at.desc()).all()

    @staticmethod
    def get_model_by_id(db: Session, model_id: str) -> Optional[ModelRegistry]:
        """获取模型详情"""
        return db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()

    @staticmethod
    def create_model(db: Session, data: ModelRegistryCreate) -> ModelRegistry:
        """注册模型"""
        model = ModelRegistry(**data.model_dump())
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def update_model_status(db: Session, model_id: str, status: str) -> Optional[ModelRegistry]:
        """更新模型状态 (candidate → champion → retired)"""
        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == model_id).first()
        if model:
            model.status = status
            db.commit()
            db.refresh(model)
        return model

    @staticmethod
    def get_champion_model(db: Session) -> Optional[ModelRegistry]:
        """获取当前champion模型"""
        return db.query(ModelRegistry).filter(ModelRegistry.status == "champion").first()
