from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, JSON, Text, Index, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base


class Backtest(Base):
    """回测任务表"""
    __tablename__ = "backtests"
    __table_args__ = (
        Index("ix_bt_model", "model_id"),
        Index("ix_bt_status", "status"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True, nullable=False)
    job_name: str = Column(String(100), nullable=False)
    benchmark_code: str = Column(String(20))  # 基准指数
    start_date: Date = Column(Date, nullable=False)
    end_date: Date = Column(Date, nullable=False)
    initial_capital: float = Column(Float, default=1000000.0)
    # 交易成本配置
    commission_rate: float = Column(Float, default=0.00025)  # 佣金率
    stamp_tax_rate: float = Column(Float, default=0.001)  # 印花税率(卖出)
    slippage_rate: float = Column(Float, default=0.001)  # 滑点率
    transfer_fee_rate: float = Column(Float, default=0.00001)  # 过户费率
    # 执行配置
    execution_mode: str = Column(String(20), default="open")  # open, vwap, close
    rebalance_freq: str = Column(String(20), default="weekly")  # daily, weekly, biweekly, monthly
    holding_count: int = Column(Integer, default=50)  # 持仓数量
    # 状态
    status: str = Column(String(20), default="pending")  # pending, running, success, failed
    progress: float = Column(Float, default=0.0)  # 进度 0-100
    error_message: Text = Column(Text)
    result_path: str = Column(String(255))
    # 元数据
    created_by: int = Column(Integer)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Backtest(id={self.id}, model_id={self.model_id}, job_name='{self.job_name}')>"


class BacktestNav(Base):
    """回测净值表"""
    __tablename__ = "backtest_navs"
    __table_args__ = (
        Index("ix_bn_bt_date", "backtest_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    backtest_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, nullable=False)
    nav: float = Column(Float)  # 策略净值
    benchmark_nav: float = Column(Float)  # 基准净值
    excess_nav: float = Column(Float)  # 超额净值
    drawdown: float = Column(Float)  # 回撤
    cash: float = Column(Float)  # 现金
    position_value: float = Column(Float)  # 持仓市值
    created_at: DateTime = Column(DateTime, server_default=func.now())


class BacktestPosition(Base):
    """回测持仓表"""
    __tablename__ = "backtest_positions"
    __table_args__ = (
        Index("ix_bp_bt_date", "backtest_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    backtest_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, nullable=False)
    security_id: str = Column(String(20), nullable=False)
    weight: float = Column(Float)  # 权重
    shares: int = Column(Integer)  # 股数
    market_value: float = Column(Float)  # 市值
    cost_price: float = Column(Float)  # 成本价
    created_at: DateTime = Column(DateTime, server_default=func.now())


class BacktestTrade(Base):
    """回测成交表"""
    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index("ix_bt_trade_bt_date", "backtest_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    backtest_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, nullable=False)
    security_id: str = Column(String(20), nullable=False)
    action: str = Column(String(10), nullable=False)  # buy, sell
    price: float = Column(Float)  # 成交价
    quantity: int = Column(Integer)  # 成交量(股)
    amount: float = Column(Float)  # 成交额
    commission: float = Column(Float, default=0)  # 佣金
    stamp_tax: float = Column(Float, default=0)  # 印花税
    transfer_fee: float = Column(Float, default=0)  # 过户费
    slippage: float = Column(Float, default=0)  # 滑点
    total_cost: float = Column(Float, default=0)  # 总成本
    trade_status: str = Column(String(20), default="success")  # success, failed
    fail_reason: str = Column(String(200))  # 失败原因
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<BacktestTrade(backtest_id={self.backtest_id}, trade_date='{self.trade_date}', action='{self.action}')>"


class BacktestResult(Base):
    """回测指标汇总表"""
    __tablename__ = "backtest_results"
    __table_args__ = (
        Index("ix_br_bt", "backtest_id"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    backtest_id: int = Column(Integer, index=True, nullable=False)
    # 收益指标
    total_return: float = Column(Float)
    annual_return: float = Column(Float)
    benchmark_return: float = Column(Float)
    excess_return: float = Column(Float)
    annual_excess_return: float = Column(Float)
    # 风险指标
    max_drawdown: float = Column(Float)
    max_drawdown_duration: int = Column(Integer)  # 最大回撤持续天数
    volatility: float = Column(Float)  # 年化波动率
    downside_volatility: float = Column(Float)  # 下行波动率
    # 风险调整收益
    sharpe: float = Column(Float)
    sortino: float = Column(Float)
    calmar: float = Column(Float)
    information_ratio: float = Column(Float)
    # 其他指标
    turnover_rate: float = Column(Float)
    win_rate: float = Column(Float)
    profit_loss_ratio: float = Column(Float)
    alpha: float = Column(Float)
    beta: float = Column(Float)
    # 扩展数据
    metrics_json: JSON = Column(JSON)  # 扩展指标
    monthly_returns: JSON = Column(JSON)  # 月度收益
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<BacktestResult(backtest_id={self.backtest_id}, annual_return={self.annual_return})>"