"""核心量化模块 — 因子引擎、评分、择时、回测、风控等。"""

from app.core.adaptive_factor_engine import AdaptiveFactorEngine, FactorState, FactorProfile
from app.core.online_learning import OnlineLearning
from app.core.risk_budget_engine import RiskBudgetEngine, RiskLimit, RiskAction
from app.core.alpha_modules import AlphaModule, PriceAlphaModule, FundamentalAlphaModule, RevisionAlphaModule, FlowEventAlphaModule, get_module, get_all_modules
from app.core.ensemble import AlphaEnsemble
from app.core.factor_monitor import FactorMonitor
from app.core.labels import LabelBuilder
from app.core.regime import RegimeDetector, REGIME_TRENDING, REGIME_MEAN_REVERTING, REGIME_DEFENSIVE, REGIME_RISK_ON
from app.core.universe import UniverseBuilder

__all__ = [
    "AdaptiveFactorEngine",
    "FactorState",
    "FactorProfile",
    "OnlineLearning",
    "RiskBudgetEngine",
    "RiskLimit",
    "RiskAction",
    # GPT设计新增模块
    "AlphaModule",
    "PriceAlphaModule",
    "FundamentalAlphaModule",
    "RevisionAlphaModule",
    "FlowEventAlphaModule",
    "get_module",
    "get_all_modules",
    "AlphaEnsemble",
    "FactorMonitor",
    "LabelBuilder",
    "RegimeDetector",
    "REGIME_TRENDING",
    "REGIME_MEAN_REVERTING",
    "REGIME_DEFENSIVE",
    "REGIME_RISK_ON",
    "UniverseBuilder",
]