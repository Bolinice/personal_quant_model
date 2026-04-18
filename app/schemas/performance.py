from datetime import datetime
from pydantic import BaseModel, ConfigDict, ConfigDict
from typing import Optional, Dict, List, Any


class PerformanceBase(BaseModel):
    performance_type: str  # portfolio, factor, model
    entity_id: int
    metric_name: str
    metric_value: float
    trade_date: datetime

class PerformanceCreate(PerformanceBase):
    pass

class PerformanceUpdate(BaseModel):
    metric_value: Optional[float] = None

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
    information_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    volatility: Optional[float] = None
    win_rate: Optional[float] = None
    profit_loss_ratio: Optional[float] = None
    turnover_rate: Optional[float] = None


class PerformanceReport(BaseModel):
    """绩效报告"""
    analysis: PerformanceAnalysis
    industry_exposure: Optional[Dict[str, float]] = None
    style_exposure: Optional[Dict[str, float]] = None
    monthly_returns: Optional[List[Dict[str, Any]]] = None
    top_holdings: Optional[List[Dict[str, Any]]] = None
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)