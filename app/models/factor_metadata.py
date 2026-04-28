"""因子元数据模型"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class FactorMetadata(Base):
    """因子元数据表 - 因子身份证"""

    __tablename__ = "factor_metadata"

    factor_name = Column(String(100), primary_key=True, comment="因子名称")
    factor_group = Column(
        String(50),
        nullable=False,
        index=True,
        comment="因子组: quality_growth/expectation/residual_momentum/flow_confirm/risk_penalty/experimental",
    )
    description = Column(Text, comment="因子描述")
    formula = Column(Text, comment="计算公式")
    source_table = Column(String(100), comment="来源表")
    pit_required = Column(Boolean, default=False, comment="是否需要PIT对齐")
    direction = Column(Integer, default=1, comment="方向: 1=越大越好, -1=越小越好")
    frequency = Column(String(20), default="daily", comment="频率: daily/weekly/monthly/quarterly")
    status = Column(String(20), default="experimental", comment="状态: experimental/candidate/production/deprecated")
    version = Column(String(20), default="1.0", comment="版本号")
    coverage_threshold = Column(Integer, default=70, comment="最低覆盖率要求(%)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = ({"comment": "因子元数据表"},)
