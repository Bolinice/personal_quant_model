"""
多因子模型相关的Schema定义
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.core.multi_factor_model import FactorWeightingMethod
from app.core.portfolio_builder import PortfolioMode


class MultiFactorRunRequest(BaseModel):
    """多因子模型运行请求"""

    ts_codes: list[str] = Field(..., description="股票池代码列表")
    trade_date: date = Field(..., description="交易日期")
    total_value: float = Field(..., description="总资产", gt=0)
    current_holdings: dict[str, float] | None = Field(None, description="当前持仓 {ts_code: shares}")
    factor_groups: list[str] | None = Field(None, description="使用的因子组，None表示使用所有")
    weighting_method: str = Field(
        FactorWeightingMethod.EQUAL, description="因子加权方法: equal/ic/ir/historical_return"
    )
    neutralize_industry: bool = Field(True, description="是否行业中性化")
    neutralize_market_cap: bool = Field(True, description="是否市值中性化")
    top_n: int = Field(60, description="选择前N只股票", gt=0, le=200)
    exclude_list: list[str] | None = Field(None, description="排除列表（ST、停牌等）")


class MultiFactorRunResponse(BaseModel):
    """多因子模型运行响应"""

    trade_date: date = Field(..., description="交易日期")
    target_holdings: dict[str, float] = Field(..., description="目标持仓 {ts_code: shares}")
    trades: list[dict[str, Any]] = Field(..., description="交易列表")
    portfolio_value: float = Field(..., description="组合总值")
    position_count: int = Field(..., description="持仓数量")


class PortfolioResponse(BaseModel):
    """组合构建响应"""

    target_holdings: dict[str, float] = Field(..., description="目标持仓")
    trades: list[dict[str, Any]] = Field(..., description="交易列表")
    portfolio_value: float = Field(..., description="组合总值")
    position_count: int = Field(..., description="持仓数量")


class MultiFactorModelConfig(BaseModel):
    """多因子模型配置"""

    available_factor_groups: list[str] = Field(..., description="可用的因子组")
    weighting_methods: list[str] = Field(..., description="可用的加权方法")
    portfolio_modes: list[str] = Field(..., description="可用的组合模式")
    default_top_n: int = Field(..., description="默认选股数量")
    default_lookback_days: int = Field(..., description="默认回溯天数")
