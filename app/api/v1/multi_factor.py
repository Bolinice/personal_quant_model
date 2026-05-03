"""
多因子模型API端点
提供多因子选股模型的完整功能
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.logging import logger
from app.core.multi_factor_model import FactorWeightingMethod, MultiFactorModel
from app.core.portfolio_builder import PortfolioMode
from app.schemas.multi_factor import (
    MultiFactorModelConfig,
    MultiFactorRunRequest,
    MultiFactorRunResponse,
    PortfolioResponse,
)

router = APIRouter()


@router.post("/run", response_model=MultiFactorRunResponse)
def run_multi_factor_model(
    request: MultiFactorRunRequest,
    db: Session = Depends(get_db),
) -> MultiFactorRunResponse:
    """
    运行多因子选股模型

    完整流程：
    1. 因子计算
    2. 因子预处理（去极值、标准化、中性化）
    3. 因子合成
    4. 选股
    5. 组合构建

    Args:
        request: 模型运行请求
        db: 数据库会话

    Returns:
        模型运行结果，包含选中的股票和组合信息
    """
    try:
        logger.info(f"Running multi-factor model for {request.trade_date}")

        # 初始化模型
        model = MultiFactorModel(
            db=db,
            factor_groups=request.factor_groups,
            weighting_method=request.weighting_method,
            neutralize_industry=request.neutralize_industry,
            neutralize_market_cap=request.neutralize_market_cap,
        )

        # 运行模型
        result = model.run(
            ts_codes=request.ts_codes,
            trade_date=request.trade_date,
            total_value=request.total_value,
            current_holdings=request.current_holdings,
            top_n=request.top_n,
            exclude_list=request.exclude_list,
        )

        return MultiFactorRunResponse(
            trade_date=request.trade_date,
            target_holdings=result.get("target_holdings", {}),
            trades=result.get("trades", []),
            portfolio_value=result.get("portfolio_value", request.total_value),
            position_count=len(result.get("target_holdings", {})),
        )

    except Exception as e:
        logger.error(f"Error running multi-factor model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-factors")
def calculate_factors(
    ts_codes: list[str],
    trade_date: date,
    factor_groups: list[str] | None = None,
    lookback_days: int = 252,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    计算因子值

    Args:
        ts_codes: 股票代码列表
        trade_date: 计算日期
        factor_groups: 因子组列表
        lookback_days: 回溯天数
        db: 数据库会话

    Returns:
        因子数据
    """
    try:
        model = MultiFactorModel(db=db, factor_groups=factor_groups)
        factor_df = model.calculate_factors(ts_codes, trade_date, lookback_days)

        return {
            "trade_date": str(trade_date),
            "stock_count": len(factor_df),
            "factor_count": len(factor_df.columns) - 1,
            "factors": factor_df.to_dict(orient="records"),
        }

    except Exception as e:
        logger.error(f"Error calculating factors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preprocess-factors")
def preprocess_factors(
    factor_data: dict[str, Any],
    neutralize_industry: bool = True,
    neutralize_market_cap: bool = True,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    因子预处理

    Args:
        factor_data: 因子数据
        neutralize_industry: 是否行业中性化
        neutralize_market_cap: 是否市值中性化
        db: 数据库会话

    Returns:
        预处理后的因子数据
    """
    try:
        import pandas as pd

        factor_df = pd.DataFrame(factor_data.get("factors", []))

        model = MultiFactorModel(
            db=db,
            neutralize_industry=neutralize_industry,
            neutralize_market_cap=neutralize_market_cap,
        )

        processed_df = model.preprocess_factors(factor_df)

        return {
            "stock_count": len(processed_df),
            "factor_count": len(processed_df.columns) - 1,
            "factors": processed_df.to_dict(orient="records"),
        }

    except Exception as e:
        logger.error(f"Error preprocessing factors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/composite-factors")
def composite_factors(
    factor_data: dict[str, Any],
    weighting_method: str = FactorWeightingMethod.EQUAL,
    factor_weights: dict[str, float] | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    因子合成

    Args:
        factor_data: 因子数据
        weighting_method: 加权方法
        factor_weights: 因子权重
        db: 数据库会话

    Returns:
        综合得分数据
    """
    try:
        import pandas as pd

        factor_df = pd.DataFrame(factor_data.get("factors", []))

        model = MultiFactorModel(db=db, weighting_method=weighting_method)

        composite_df = model.composite_factors(factor_df, factor_weights)

        return {
            "stock_count": len(composite_df),
            "scores": composite_df.to_dict(orient="records"),
        }

    except Exception as e:
        logger.error(f"Error compositing factors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/select-stocks")
def select_stocks(
    composite_data: dict[str, Any],
    top_n: int = 60,
    exclude_list: list[str] | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    选股

    Args:
        composite_data: 综合得分数据
        top_n: 选择前N只股票
        exclude_list: 排除列表
        db: 数据库会话

    Returns:
        选中的股票
    """
    try:
        import pandas as pd

        composite_df = pd.DataFrame(composite_data.get("scores", []))

        model = MultiFactorModel(db=db)

        selected_df = model.select_stocks(composite_df, top_n, exclude_list)

        return {
            "selected_count": len(selected_df),
            "stocks": selected_df.to_dict(orient="records"),
        }

    except Exception as e:
        logger.error(f"Error selecting stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build-portfolio", response_model=PortfolioResponse)
def build_portfolio(
    selected_data: dict[str, Any],
    total_value: float,
    current_holdings: dict[str, float] | None = None,
    mode: PortfolioMode = PortfolioMode.PRODUCTION,
    db: Session = Depends(get_db),
) -> PortfolioResponse:
    """
    构建投资组合

    Args:
        selected_data: 选中的股票数据
        total_value: 总资产
        current_holdings: 当前持仓
        mode: 组合构建模式
        db: 数据库会话

    Returns:
        组合信息
    """
    try:
        import pandas as pd

        selected_df = pd.DataFrame(selected_data.get("stocks", []))

        model = MultiFactorModel(db=db)

        portfolio = model.build_portfolio(selected_df, total_value, current_holdings, mode)

        return PortfolioResponse(
            target_holdings=portfolio.get("target_holdings", {}),
            trades=portfolio.get("trades", []),
            portfolio_value=portfolio.get("portfolio_value", total_value),
            position_count=len(portfolio.get("target_holdings", {})),
        )

    except Exception as e:
        logger.error(f"Error building portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
def get_model_config() -> MultiFactorModelConfig:
    """
    获取模型配置选项

    Returns:
        模型配置信息
    """
    from app.core.factor_calculator import FACTOR_GROUPS

    return MultiFactorModelConfig(
        available_factor_groups=list(FACTOR_GROUPS.keys()),
        weighting_methods=[
            FactorWeightingMethod.EQUAL,
            FactorWeightingMethod.IC,
            FactorWeightingMethod.IR,
            FactorWeightingMethod.HISTORICAL_RETURN,
        ],
        portfolio_modes=[PortfolioMode.RESEARCH, PortfolioMode.PRODUCTION],
        default_top_n=60,
        default_lookback_days=252,
    )
