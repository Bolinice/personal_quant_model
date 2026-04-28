from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PerformanceBase(BaseModel):
    performance_type: str  # portfolio, factor, model
    entity_id: int
    metric_name: str
    metric_value: float
    trade_date: datetime


class PerformanceCreate(PerformanceBase):
    pass


class PerformanceUpdate(BaseModel):
    metric_value: float | None = None


class PerformanceInDB(PerformanceBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PerformanceOut(PerformanceBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Performance(PerformanceOut):
    pass


class PerformanceAnalysis(BaseModel):
    """绩效分析结果"""

    total_return: float
    annual_return: float
    benchmark_return: float
    excess_return: float
    max_drawdown: float
    sharpe_ratio: float
    calmar_ratio: float
    information_ratio: float | None = None
    sortino_ratio: float | None = None
    volatility: float | None = None
    win_rate: float | None = None
    profit_loss_ratio: float | None = None
    turnover_rate: float | None = None


class PerformanceReport(BaseModel):
    """绩效报告"""

    analysis: PerformanceAnalysis
    industry_exposure: dict[str, float] | None = None
    style_exposure: dict[str, float] | None = None
    monthly_returns: list[dict[str, Any]] | None = None
    top_holdings: list[dict[str, Any]] | None = None
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
