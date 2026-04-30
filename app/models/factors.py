from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class Factor(Base):
    """因子定义表"""

    __tablename__ = "factors"
    __table_args__ = (
        UniqueConstraint("factor_code", name="uq_factor_code"),
        Index("ix_factor_category", "category"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    factor_code: str = Column(String(50), unique=True, index=True, nullable=False)
    factor_name: str = Column(String(100), nullable=False)
    category: str = Column(String(50))  # quality, valuation, momentum, growth, risk, liquidity
    sub_category: str = Column(String(50))  # 子分类
    formula_desc: Text = Column(Text)  # 公式描述
    parameter_config: JSON = Column(JSON)  # 参数配置
    direction: int = Column(Integer, default=1)  # 1正向(越大越好), -1反向(越小越好)
    calc_expression: str = Column(String(500))
    description: str = Column(String(500))
    is_active: bool = Column(Boolean, default=True)
    created_by: int = Column(Integer)  # 创建人
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Factor(id={self.id}, factor_code='{self.factor_code}', factor_name='{self.factor_name}')>"


class FactorValue(Base):
    """因子值结果表 - 支持raw/processed/neutralized/zscore多级存储"""

    __tablename__ = "factor_values"
    __table_args__ = (
        UniqueConstraint("factor_id", "trade_date", "security_id", name="uq_fv_factor_date_sec"),
        Index("ix_fv_factor_date_stock", "factor_id", "trade_date", "security_id"),
        Index("ix_fv_date_stock", "trade_date", "security_id"),
        Index("ix_fv_factor_date", "factor_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    factor_id: int = Column(Integer, index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    security_id: str = Column(String(20), index=True, nullable=False)  # ts_code
    raw_value: float = Column(Float)  # 原始值
    processed_value: float = Column(Float)  # 预处理后值
    neutralized_value: float = Column(Float)  # 中性化后值
    zscore_value: float = Column(Float)  # 标准化值
    value: float = Column(Float)  # 最终使用值(兼容旧接口)
    coverage_flag: bool = Column(Boolean, default=True)  # 是否有效
    is_valid: bool = Column(Boolean, default=True)
    run_id: str = Column(String(50))  # 任务运行ID
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return (
            f"<FactorValue(factor_id={self.factor_id}, trade_date='{self.trade_date}', security_id={self.security_id})>"
        )


class FactorAnalysis(Base):
    """因子分析结果表"""

    __tablename__ = "factor_analysis"
    __table_args__ = (
        UniqueConstraint("factor_id", "analysis_date", "analysis_type", name="uq_fa_factor_date_type"),
        Index("ix_fa_factor_date", "factor_id", "analysis_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    factor_id: int = Column(Integer, index=True, nullable=False)
    analysis_type: str = Column(String(30))  # ic, rank_ic, group, decay, correlation
    analysis_date: Date = Column(Date, index=True)
    start_date: Date = Column(Date)
    end_date: Date = Column(Date)
    benchmark_code: str = Column(String(20))
    # IC指标
    ic: float = Column(Float)
    rank_ic: float = Column(Float)
    ic_ir: float = Column(Float)  # ICIR
    rank_ic_ir: float = Column(Float)  # RankIC IR
    # 统计指标
    mean: float = Column(Float)
    std: float = Column(Float)
    quantile_25: float = Column(Float)
    quantile_50: float = Column(Float)
    quantile_75: float = Column(Float)
    coverage: float = Column(Float)
    # 扩展数据
    ic_decay: JSON = Column(JSON)  # IC衰减序列
    group_returns: JSON = Column(JSON)  # 分组收益
    long_short_return: float = Column(Float)  # 多空收益
    correlation: float = Column(Float)  # 因子相关性
    compare_factor_id: int = Column(Integer)  # 对比因子ID
    result_json: JSON = Column(JSON)  # 扩展结果
    report_path: str = Column(String(255))  # 报告路径
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<FactorAnalysis(factor_id={self.factor_id}, type='{self.analysis_type}', date='{self.analysis_date}')>"


class FactorResult(Base):
    """因子评分结果表"""

    __tablename__ = "factor_results"
    __table_args__ = (
        UniqueConstraint("factor_id", "security_id", "trade_date", name="uq_fr_factor_sec_date"),
        Index("ix_fr_factor_date", "factor_id", "trade_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    factor_id: int = Column(Integer, index=True, nullable=False)
    security_id: str = Column(String(20), index=True, nullable=False)
    trade_date: Date = Column(Date, index=True, nullable=False)
    score: float = Column(Float)  # 标准化得分
    rank: int = Column(Integer)  # 排名
    quantile: int = Column(Integer)  # 分位
    is_selected: bool = Column(Boolean, default=False)  # 是否选中
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<FactorResult(factor_id={self.factor_id}, security_id={self.security_id}, trade_date='{self.trade_date}', score={self.score})>"
