"""模型健康监控表"""

from sqlalchemy import Column, BigInteger, String, Date, Numeric
from app.db.base import Base


class MonitorModelHealth(Base):
    """模型健康监控表 - 预测漂移/特征重要性变化/OOS偏差"""
    __tablename__ = "monitor_model_health"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True, comment="交易日")
    model_id = Column(String(100), nullable=False, index=True, comment="模型ID")
    prediction_drift = Column(Numeric(10, 6), comment="预测漂移")
    feature_importance_drift = Column(Numeric(10, 6), comment="特征重要性漂移")
    oos_score = Column(Numeric(10, 6), comment="OOS分数")
    health_status = Column(String(20), default="healthy", comment="健康状态: healthy/warning/critical")

    __table_args__ = (
        {"comment": "模型健康监控表"},
    )