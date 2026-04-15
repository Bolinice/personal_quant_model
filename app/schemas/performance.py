from pydantic import BaseModel, Field
from datetime import date
from typing import Dict, List, Optional

class PerformanceMetrics(BaseModel):
    total_return: float = Field(description="累计收益率")
    annual_return: float = Field(description="年化收益率")
    benchmark_return: float = Field(description="基准收益率")
    excess_return: float = Field(description="超额收益率")
    max_drawdown: float = Field(description="最大回撤")
    sharpe: float = Field(description="夏普比率")
    calmar: float = Field(description="卡玛比率")
    information_ratio: float = Field(description="信息比率")
    turnover_rate: float = Field(description="换手率")
    win_rate: float = Field(description="胜率")

class PerformanceChart(BaseModel):
    dates: List[date] = Field(description="日期列表")
    nav: List[float] = Field(description="净值列表")
    cum_return: List[float] = Field(description="累计收益率列表")
    drawdown: List[float] = Field(description="回撤列表")

class IndustryExposure(BaseModel):
    industry_name: str = Field(description="行业名称")
    weight: float = Field(description="权重")

class StyleExposure(BaseModel):
    market_cap: float = Field(description="市值暴露")
    value: float = Field(description="估值暴露")
    growth: float = Field(description="成长暴露")

class PerformanceAnalysis(BaseModel):
    metrics: PerformanceMetrics = Field(description="绩效指标")
    monthly_returns: Dict[str, float] = Field(description="月度收益率")
    performance_chart: PerformanceChart = Field(description="绩效图表")
    industry_exposure: List[IndustryExposure] = Field(description="行业暴露")
    style_exposure: StyleExposure = Field(description="风格暴露")

class PerformanceReport(BaseModel):
    summary: Dict[str, str] = Field(description="报告摘要")
    charts: PerformanceChart = Field(description="图表数据")
    monthly_returns: Dict[str, str] = Field(description="月度收益率")
    industry_exposure: List[IndustryExposure] = Field(description="行业暴露")
    style_exposure: StyleExposure = Field(description="风格暴露")