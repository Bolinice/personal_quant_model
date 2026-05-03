"""
模型数据Repository
==================
负责模型元数据的查询和存储

设计原则:
- 所有方法返回字典或基础数据类型
- 支持批量操作
- 统一异常处理
"""

from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.models import Model
from app.core.exceptions import DatabaseException
from app.core.retry import retry_on_db_connection_error, retry_on_db_deadlock


class ModelRepository:
    """模型数据Repository"""

    def __init__(self, session: Session):
        self.session = session

    # ==================== 查询模型 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_model_by_id(self, model_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取模型记录

        Args:
            model_id: 模型ID

        Returns:
            模型记录字典，不存在返回None

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            model = self.session.query(Model).filter(Model.id == model_id).first()

            if not model:
                return None

            return {
                "id": model.id,
                "name": model.name,
                "description": model.description,
                "model_type": model.model_type,
                "config": model.config,
                "status": model.status,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            }

        except Exception as e:
            raise DatabaseException(
                message=f"查询模型记录失败: {model_id}",
                context={"model_id": model_id, "error": str(e)},
                retryable=False,
            ) from e

    @retry_on_db_connection_error(max_attempts=3)
    def get_models(
        self,
        model_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        查询模型列表

        Args:
            model_type: 模型类型（None表示全部）
            status: 状态（None表示全部）
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            模型记录列表

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = self.session.query(Model)

            if model_type:
                query = query.filter(Model.model_type == model_type)

            if status:
                query = query.filter(Model.status == status)

            query = query.order_by(Model.created_at.desc()).offset(skip).limit(limit)

            models = query.all()

            return [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "model_type": m.model_type,
                    "config": m.config,
                    "status": m.status,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in models
            ]

        except Exception as e:
            raise DatabaseException(
                message="查询模型列表失败",
                context={
                    "model_type": model_type,
                    "status": status,
                    "skip": skip,
                    "limit": limit,
                    "error": str(e),
                },
                retryable=False,
            ) from e

    # ==================== 创建模型 ====================

    @retry_on_db_deadlock(max_attempts=3)
    def create_model(self, data: Dict[str, Any]) -> int:
        """
        创建模型记录

        Args:
            data: 模型数据字典

        Returns:
            模型ID

        Raises:
            DatabaseException: 数据库创建失败
        """
        try:
            model = Model(**data)
            self.session.add(model)
            self.session.commit()
            self.session.refresh(model)

            return model.id

        except Exception as e:
            self.session.rollback()
            raise DatabaseException(
                message="创建模型记录失败",
                context={"data": data, "error": str(e)},
                retryable=True,
            ) from e

    # ==================== 更新模型 ====================

    @retry_on_db_deadlock(max_attempts=3)
    def update_model(self, model_id: int, data: Dict[str, Any]) -> bool:
        """
        更新模型记录

        Args:
            model_id: 模型ID
            data: 更新数据字典

        Returns:
            是否更新成功

        Raises:
            DatabaseException: 数据库更新失败
        """
        try:
            model = self.session.query(Model).filter(Model.id == model_id).first()

            if not model:
                return False

            for key, value in data.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            raise DatabaseException(
                message=f"更新模型记录失败: {model_id}",
                context={"model_id": model_id, "data": data, "error": str(e)},
                retryable=True,
            ) from e

    # ==================== 删除模型 ====================

    @retry_on_db_deadlock(max_attempts=3)
    def delete_model(self, model_id: int) -> bool:
        """
        删除模型记录

        Args:
            model_id: 模型ID

        Returns:
            是否删除成功

        Raises:
            DatabaseException: 数据库删除失败
        """
        try:
            model = self.session.query(Model).filter(Model.id == model_id).first()

            if not model:
                return False

            self.session.delete(model)
            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            raise DatabaseException(
                message=f"删除模型记录失败: {model_id}",
                context={"model_id": model_id, "error": str(e)},
                retryable=True,
            ) from e
