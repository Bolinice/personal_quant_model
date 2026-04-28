"""模型注册表"""

from sqlalchemy import Column, Date, DateTime, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class ModelRegistry(Base):
    """模型注册表 - 模型版本管理与实验治理"""

    __tablename__ = "model_registry"

    model_id = Column(String(100), primary_key=True, comment="模型ID")
    model_name = Column(String(200), nullable=False, comment="模型名称")
    model_type = Column(String(50), comment="模型类型: linear/tree/nn/ensemble")
    feature_set_version = Column(String(50), comment="特征集版本")
    label_version = Column(String(50), comment="标签版本")
    train_start = Column(Date, comment="训练开始日期")
    train_end = Column(Date, comment="训练结束日期")
    valid_start = Column(Date, comment="验证开始日期")
    valid_end = Column(Date, comment="验证结束日期")
    params_json = Column(Text, comment="超参数JSON")
    oof_metric_json = Column(Text, comment="OOF指标JSON")
    status = Column(String(20), default="candidate", comment="状态: candidate/champion/retired")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = ({"comment": "模型注册表"},)
