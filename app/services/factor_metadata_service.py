"""因子元数据服务"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.factor_metadata import FactorMetadata
from app.schemas.factor_metadata import FactorMetadataCreate


class FactorMetadataService:
    """因子元数据服务"""

    @staticmethod
    def get_all_factors(
        db: Session,
        factor_group: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[FactorMetadata]:
        """获取因子列表"""
        query = db.query(FactorMetadata)
        if factor_group:
            query = query.filter(FactorMetadata.factor_group == factor_group)
        if status:
            query = query.filter(FactorMetadata.status == status)
        return query.all()

    @staticmethod
    def get_factor_by_name(db: Session, factor_name: str) -> Optional[FactorMetadata]:
        """获取因子详情"""
        return db.query(FactorMetadata).filter(FactorMetadata.factor_name == factor_name).first()

    @staticmethod
    def create_factor(db: Session, data: FactorMetadataCreate) -> FactorMetadata:
        """创建因子元数据"""
        factor = FactorMetadata(**data.model_dump())
        db.add(factor)
        db.commit()
        db.refresh(factor)
        return factor

    @staticmethod
    def update_factor_status(db: Session, factor_name: str, status: str) -> Optional[FactorMetadata]:
        """更新因子状态"""
        factor = db.query(FactorMetadata).filter(FactorMetadata.factor_name == factor_name).first()
        if factor:
            factor.status = status
            db.commit()
            db.refresh(factor)
        return factor
