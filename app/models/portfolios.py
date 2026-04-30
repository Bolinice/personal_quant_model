from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class Portfolio(Base):
    """目标组合表"""

    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("model_id", "trade_date", "portfolio_version", name="uq_portfolio_model_date_ver"),
        Index("ix_port_model", "model_id"),
        Index("ix_port_date", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    portfolio_version: str = Column(String(20))  # 组合版本
    target_exposure: float = Column(Float, default=1.0)  # 目标仓位
    total_weight: float = Column(Float)  # 总权重
    generated_by_run_id: str = Column(String(50))  # 生成任务ID
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Portfolio(id={self.id}, model_id={self.model_id}, trade_date='{self.trade_date}')>"


class PortfolioPosition(Base):
    """目标持仓明细表"""

    __tablename__ = "portfolio_positions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "security_id", name="uq_pp_port_sec"),
        Index("ix_pp_portfolio", "portfolio_id"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    portfolio_id: int = Column(Integer, index=True, nullable=False)
    security_id: str = Column(String(20), nullable=False)
    target_weight: float = Column(Float)  # 目标权重
    score: float = Column(Float)  # 综合分
    industry_code: str = Column(String(20))  # 行业
    liquidity_tag: str = Column(String(20))  # 流动性标签
    remark: str = Column(String(200))  # 备注
    created_at: DateTime = Column(DateTime, server_default=func.now())


class RebalanceRecord(Base):
    """调仓记录表"""

    __tablename__ = "rebalance_records"
    __table_args__ = (
        UniqueConstraint("model_id", "trade_date", name="uq_rr_model_date"),
        Index("ix_rr_model_date", "model_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    rebalance_type: str = Column(String(20))  # scheduled, signal, risk
    buy_list: JSON = Column(JSON)  # 买入列表
    sell_list: JSON = Column(JSON)  # 卖出列表
    adjust_list: JSON = Column(JSON)  # 调整列表
    total_turnover: float = Column(Float)  # 总换手率
    est_amount: float = Column(Float)  # 预估成交额
    est_cost: float = Column(Float)  # 预估成本
    order_status: str = Column(String(20), default="pending")  # pending, executed, failed
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return (
            f"<RebalanceRecord(model_id={self.model_id}, trade_date='{self.trade_date}', type='{self.rebalance_type}')>"
        )


class TimingSignal(Base):
    """择时信号表"""

    __tablename__ = "timing_signals"
    __table_args__ = (
        UniqueConstraint("model_id", "trade_date", "signal_type", name="uq_ts_model_date_type"),
        Index("ix_ts_model_date", "model_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    signal_type: str = Column(String(20))  # long, short, neutral
    signal_value: float = Column(Float)  # 信号值
    target_exposure: float = Column(Float)  # 目标仓位
    signal_detail: JSON = Column(JSON)  # 信号细节
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<TimingSignal(model_id={self.model_id}, trade_date='{self.trade_date}', signal_type='{self.signal_type}')>"


class TimingConfig(Base):
    """择时配置表"""

    __tablename__ = "timing_configs"

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, unique=True, index=True)
    config_type: str = Column(String(50))  # ma_timing, breadth_timing, volatility_timing, drawdown_timing
    config_params: JSON = Column(JSON)
    is_active: bool = Column(Boolean, default=True)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())
