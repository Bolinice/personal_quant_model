"""因子健康监控表"""

from sqlalchemy import Column, BigInteger, String, Date, Numeric
from app.db.base import Base


class MonitorFactorHealth(Base):
    """因子健康监控表 - IC/PSI/覆盖率/缺失率"""
    __tablename__ = "monitor_factor_health"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True, comment="交易日")
    factor_name = Column(String(100), nullable=False, index=True, comment="因子名")
    coverage_rate = Column(Numeric(6, 4), comment="覆盖率")
    missing_rate = Column(Numeric(6, 4), comment="缺失率")
    ic_rolling = Column(Numeric(10, 6), comment="滚动IC")
    ic_mean = Column(Numeric(10, 6), comment="IC均值")
    icir = Column(Numeric(10, 6), comment="ICIR(IC信息比率)")
    psi = Column(Numeric(10, 6), comment="PSI(群体稳定性指数)")
    health_status = Column(String(20), default="healthy", comment="健康状态: healthy/warning/critical")

    __table_args__ = (
        {"comment": "因子健康监控表"},
    )