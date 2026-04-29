"""核心量化模块 — 因子引擎、评分、择时、回测、风控等。"""

from app.core.adaptive_factor_engine import AdaptiveFactorEngine, FactorProfile, FactorState
from app.core.alpha_modules import (
    MODULE_REGISTRY,
    ExpectationModule,
    FlowConfirmModule,
    QualityGrowthModule,
    ResidualMomentumModule,
    RiskPenaltyModule,
    get_all_modules,
    get_alpha_modules,
    get_module,
    get_risk_penalty_module,
)
from app.core.config_loader import ConfigLoader, get_config, get_config_value
from app.core.daily_pipeline import DailyPipeline
from app.core.ensemble import (
    DEFAULT_WEIGHTS,
    REGIME_WEIGHT_ADJUSTMENTS,
    EnsembleEngine,
    create_ensemble_engine,
)
from app.core.factor_monitor import FactorMonitor
from app.core.labels import LabelBuilder
from app.core.online_learning import OnlineLearning
from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode, create_portfolio_builder
from app.core.regime import REGIME_DEFENSIVE, REGIME_MEAN_REVERTING, REGIME_RISK_ON, REGIME_TRENDING, RegimeDetector
from app.core.risk_budget_engine import RiskAction, RiskBudgetEngine, RiskLimit
from app.core.universe import UniverseBuilder

__all__ = [
    "DEFAULT_WEIGHTS",
    "MODULE_REGISTRY",
    "REGIME_DEFENSIVE",
    "REGIME_MEAN_REVERTING",
    "REGIME_RISK_ON",
    "REGIME_TRENDING",
    "REGIME_WEIGHT_ADJUSTMENTS",
    "AdaptiveFactorEngine",
    # V2配置
    "ConfigLoader",
    # V2流水线
    "DailyPipeline",
    # V2融合引擎
    "EnsembleEngine",
    "ExpectationModule",
    # 其他核心模块
    "FactorMonitor",
    "FactorProfile",
    "FactorState",
    "FlowConfirmModule",
    "LabelBuilder",
    "OnlineLearning",
    # V2组合构建
    "PortfolioBuilder",
    "PortfolioMode",
    # V2 Alpha模块
    "QualityGrowthModule",
    "RegimeDetector",
    "ResidualMomentumModule",
    "RiskAction",
    "RiskBudgetEngine",
    "RiskLimit",
    "RiskPenaltyModule",
    "UniverseBuilder",
    "create_ensemble_engine",
    "create_portfolio_builder",
    "get_all_modules",
    "get_alpha_modules",
    "get_config",
    "get_config_value",
    "get_module",
    "get_risk_penalty_module",
]
