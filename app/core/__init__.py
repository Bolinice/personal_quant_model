"""核心量化模块 — 因子引擎、评分、择时、回测、风控等。"""

from app.core.adaptive_factor_engine import AdaptiveFactorEngine, FactorState, FactorProfile
from app.core.online_learning import OnlineLearning
from app.core.risk_budget_engine import RiskBudgetEngine, RiskLimit, RiskAction
from app.core.alpha_modules import (
    QualityGrowthModule,
    ExpectationModule,
    ResidualMomentumModule,
    FlowConfirmModule,
    RiskPenaltyModule,
    MODULE_REGISTRY,
    get_module,
    get_alpha_modules,
    get_risk_penalty_module,
    get_all_modules,
)
from app.core.ensemble import (
    EnsembleEngine,
    DEFAULT_WEIGHTS,
    REGIME_WEIGHT_ADJUSTMENTS,
    create_ensemble_engine,
)
from app.core.factor_monitor import FactorMonitor
from app.core.labels import LabelBuilder
from app.core.regime import RegimeDetector, REGIME_TRENDING, REGIME_MEAN_REVERTING, REGIME_DEFENSIVE, REGIME_RISK_ON
from app.core.universe import UniverseBuilder
from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode, create_portfolio_builder
from app.core.daily_pipeline import DailyPipeline
from app.core.config_loader import ConfigLoader, get_config, get_config_value

__all__ = [
    "AdaptiveFactorEngine",
    "FactorState",
    "FactorProfile",
    "OnlineLearning",
    "RiskBudgetEngine",
    "RiskLimit",
    "RiskAction",
    # V2 Alpha模块
    "QualityGrowthModule",
    "ExpectationModule",
    "ResidualMomentumModule",
    "FlowConfirmModule",
    "RiskPenaltyModule",
    "MODULE_REGISTRY",
    "get_module",
    "get_alpha_modules",
    "get_risk_penalty_module",
    "get_all_modules",
    # V2融合引擎
    "EnsembleEngine",
    "DEFAULT_WEIGHTS",
    "REGIME_WEIGHT_ADJUSTMENTS",
    "create_ensemble_engine",
    # V2组合构建
    "PortfolioBuilder",
    "PortfolioMode",
    "create_portfolio_builder",
    # V2流水线
    "DailyPipeline",
    # V2配置
    "ConfigLoader",
    "get_config",
    "get_config_value",
    # 其他核心模块
    "FactorMonitor",
    "LabelBuilder",
    "RegimeDetector",
    "REGIME_TRENDING",
    "REGIME_MEAN_REVERTING",
    "REGIME_DEFENSIVE",
    "REGIME_RISK_ON",
    "UniverseBuilder",
]