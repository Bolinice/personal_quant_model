"""
日终流水线 — 串联所有量化模块的12步执行引擎

步骤:
  1. 数据采集与PIT对齐
  2. 数据快照
  3. 股票池构建
  4. 因子计算与预处理
  5. 信号融合(Ensemble)
  6. 市场状态检测(Regime)
  7. ML增强评分
  8. 组合构建与优化
  9. 风险预算与择时
  10. 回测验证
  11. 因子健康检查
  12. 结果存档
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adaptive_factor_engine import AdaptiveFactorEngine
from app.core.backtest_engine import ABShareBacktestEngine
from app.core.ensemble import EnsembleEngine
from app.core.factor_calculator import FactorCalculator
from app.core.factor_monitor import FactorMonitor
from app.core.factor_preprocess import FactorPreprocessor
from app.core.labels import LabelBuilder
from app.core.market_timer import MarketTimer
from app.core.model_scorer import ModelScorer
from app.core.model_trainer import ModelTrainer
from app.core.pit_guard import PITGuard
from app.core.portfolio_builder import PortfolioBuilder
from app.core.portfolio_optimizer import PortfolioOptimizer
from app.core.regime import RegimeDetector
from app.core.risk_budget_engine import RiskBudgetEngine
from app.core.risk_model import RiskModel
from app.core.universe import UniverseBuilder

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """流水线单步执行结果"""
    step: int
    name: str
    status: str  # ok / error / skipped
    message: str = ""
    data: Any = None
    duration_ms: float = 0.0


@dataclass
class PipelineContext:
    """流水线上下文 — 在步骤间传递数据"""
    trade_date: date
    session: Session | None = None

    # Step 1: 数据采集
    price_df: pd.DataFrame | None = None
    financial_df: pd.DataFrame | None = None
    moneyflow_df: pd.DataFrame | None = None
    index_df: pd.DataFrame | None = None
    margin_df: pd.DataFrame | None = None
    northflow_df: pd.DataFrame | None = None

    # Step 2: 快照
    snapshot_id: str | None = None

    # Step 3: 股票池
    universe: list[str] | None = None

    # Step 4: 因子
    factor_df: pd.DataFrame | None = None
    factor_names: list[str] = field(default_factory=list)

    # Step 5: 信号融合
    ensemble_scores: pd.Series | None = None
    ensemble_weights: dict[str, float] | None = None

    # Step 6: 市场状态
    regime_state: str | None = None
    regime_confidence: float = 0.0

    # Step 7: ML增强
    ml_scores: pd.Series | None = None
    final_scores: pd.Series | None = None

    # Step 8: 组合
    portfolio_weights: pd.Series | None = None
    portfolio_stocks: list[str] = field(default_factory=list)

    # Step 9: 风险与择时
    risk_budget: dict[str, float] | None = None
    timing_signal: str | None = None
    position_ratio: float = 1.0

    # Step 10: 回测
    backtest_result: dict | None = None

    # Step 11: 因子健康
    factor_health: dict | None = None

    # Step 12: 存档
    archive_path: str | None = None


class DailyPipeline:
    """日终流水线 — 12步串联执行"""

    def __init__(
        self,
        session: Session | None = None,
        lookback_days: int = 250,
        snapshot_dir: str = "data/snapshots",
    ):
        self.session = session
        self.lookback_days = lookback_days
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各模块
        self.pit_guard = PITGuard()
        self.universe_builder = UniverseBuilder()
        self.factor_calculator = FactorCalculator()
        self.factor_preprocessor = FactorPreprocessor()
        self.ensemble_engine = EnsembleEngine()
        self.regime_detector = RegimeDetector()
        self.model_scorer = ModelScorer()
        self.model_trainer = ModelTrainer()
        self.portfolio_builder = PortfolioBuilder()
        self.portfolio_optimizer = PortfolioOptimizer()
        self.risk_model = RiskModel()
        self.market_timer = MarketTimer()
        self.risk_budget_engine = RiskBudgetEngine()
        self.backtest_engine = ABShareBacktestEngine()
        self.factor_monitor = FactorMonitor()
        self.adaptive_engine = AdaptiveFactorEngine()
        self.label_builder = LabelBuilder()

        self.results: list[PipelineResult] = []

    def run(self, trade_date: date | None = None) -> list[PipelineResult]:
        """执行完整日终流水线"""
        if trade_date is None:
            trade_date = date.today()

        ctx = PipelineContext(trade_date=trade_date, session=self.session)
        logger.info("========== 日终流水线启动 %s ==========", trade_date)

        steps = [
            (1, "数据采集与PIT对齐", self._step1_data_collection),
            (2, "数据快照", self._step2_snapshot),
            (3, "股票池构建", self._step3_universe),
            (4, "因子计算与预处理", self._step4_factor_calc),
            (5, "信号融合", self._step5_ensemble),
            (6, "市场状态检测", self._step6_regime),
            (7, "ML增强评分", self._step7_ml_scoring),
            (8, "组合构建与优化", self._step8_portfolio),
            (9, "风险预算与择时", self._step9_risk_timing),
            (10, "回测验证", self._step10_backtest),
            (11, "因子健康检查", self._step11_factor_health),
            (12, "结果存档", self._step12_archive),
        ]

        for step_num, step_name, step_fn in steps:
            t0 = pd.Timestamp.now()
            try:
                step_fn(ctx)
                result = PipelineResult(
                    step=step_num,
                    name=step_name,
                    status="ok",
                    duration_ms=(pd.Timestamp.now() - t0).total_seconds() * 1000,
                )
                logger.info("Step %2d %-20s OK (%.0fms)", step_num, step_name, result.duration_ms)
            except Exception as e:
                result = PipelineResult(
                    step=step_num,
                    name=step_name,
                    status="error",
                    message=str(e),
                    duration_ms=(pd.Timestamp.now() - t0).total_seconds() * 1000,
                )
                logger.error("Step %2d %-20s ERROR: %s", step_num, step_name, e)
                # 非关键步骤失败不中断流水线
                if step_num in (1, 3, 4, 5, 8):
                    raise

            self.results.append(result)

        logger.info("========== 日终流水线完成 %s ==========", trade_date)
        return self.results

    # ──────────────────────────────────────────────
    # Step 1: 数据采集与PIT对齐
    # ──────────────────────────────────────────────
    @staticmethod
    def _load_table(session: Session, model_cls, start_date: date, end_date: date,
                    date_col: str = "trade_date") -> pd.DataFrame | None:
        """高效加载表数据 — 使用mappings()避免ORM序列化开销"""
        stmt = (
            select(model_cls)
            .where(getattr(model_cls, date_col).between(start_date, end_date))
            .order_by(getattr(model_cls, date_col))
        )
        rows = session.execute(stmt).mappings().all()
        if rows:
            return pd.DataFrame(dict(r) for r in rows)
        return None

    def _step1_data_collection(self, ctx: PipelineContext) -> None:
        """从数据库读取行情/财务/资金流数据，PIT对齐财务数据"""
        if ctx.session is None:
            logger.warning("Step1: 无数据库会话，跳过数据采集")
            return

        start_date = ctx.trade_date - timedelta(days=self.lookback_days)

        # 1. 行情数据
        from app.models.market.stock_daily import StockDaily
        ctx.price_df = self._load_table(ctx.session, StockDaily, start_date, ctx.trade_date)
        logger.info("Step1: 行情数据 %d 条", len(ctx.price_df) if ctx.price_df is not None else 0)

        # 2. 财务数据 — PIT对齐 (SQL层过滤ann_date <= trade_date)
        from app.models.market.stock_financial import StockFinancial
        stmt = (
            select(StockFinancial)
            .where(StockFinancial.ann_date <= ctx.trade_date.strftime("%Y%m%d"))
            .order_by(StockFinancial.ann_date)
        )
        rows = ctx.session.execute(stmt).mappings().all()
        if rows:
            raw_fin = pd.DataFrame(dict(r) for r in rows)
            ctx.financial_df = self.pit_guard.align(raw_fin, ctx.trade_date)
        logger.info("Step1: 财务数据 %d 条(PIT对齐后)",
                     len(ctx.financial_df) if ctx.financial_df is not None else 0)

        # 3. 资金流数据
        from app.models.market.stock_money_flow import StockMoneyFlow
        ctx.moneyflow_df = self._load_table(ctx.session, StockMoneyFlow, start_date, ctx.trade_date)
        logger.info("Step1: 资金流数据 %d 条", len(ctx.moneyflow_df) if ctx.moneyflow_df is not None else 0)

        # 4. 指数数据
        from app.models.market.index_daily import IndexDaily
        ctx.index_df = self._load_table(ctx.session, IndexDaily, start_date, ctx.trade_date)
        logger.info("Step1: 指数数据 %d 条", len(ctx.index_df) if ctx.index_df is not None else 0)

        # 5. 融资融券数据
        try:
            from app.models.market.stock_margin import StockMargin
            ctx.margin_df = self._load_table(ctx.session, StockMargin, start_date, ctx.trade_date)
        except Exception as e:
            logger.warning("Step1: 融资融券数据读取失败: %s", e)
        logger.info("Step1: 融资融券数据 %d 条", len(ctx.margin_df) if ctx.margin_df is not None else 0)

        # 6. 北向资金数据
        try:
            from app.models.market.stock_northbound import StockNorthbound
            ctx.northflow_df = self._load_table(ctx.session, StockNorthbound, start_date, ctx.trade_date)
        except Exception as e:
            logger.warning("Step1: 北向资金数据读取失败: %s", e)
        logger.info("Step1: 北向资金数据 %d 条", len(ctx.northflow_df) if ctx.northflow_df is not None else 0)

    # ──────────────────────────────────────────────
    # Step 2: 数据快照
    # ──────────────────────────────────────────────
    def _step2_snapshot(self, ctx: PipelineContext) -> None:
        """生成数据快照ID和文件，用于可复现性"""
        snapshot_id = f"snapshot_{ctx.trade_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"
        ctx.snapshot_id = snapshot_id

        snapshot_data = {}
        for attr in ("price_df", "financial_df", "moneyflow_df", "index_df", "margin_df", "northflow_df"):
            df = getattr(ctx, attr, None)
            if df is not None:
                snapshot_data[attr] = df.to_json(orient="records", date_format="iso")

        snapshot_path = self.snapshot_dir / f"{snapshot_id}.json"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, ensure_ascii=False)

        logger.info("Step2: 快照 %s 已保存 (%.1fKB)", snapshot_id, snapshot_path.stat().st_size / 1024)

    # ──────────────────────────────────────────────
    # Step 3: 股票池构建
    # ──────────────────────────────────────────────
    def _step3_universe(self, ctx: PipelineContext) -> None:
        """构建核心股票池 — 流动性/上市天数/ST过滤"""
        if ctx.price_df is None or ctx.price_df.empty:
            raise ValueError("Step3: 无行情数据，无法构建股票池")

        ctx.universe = self.universe_builder.build_core_pool(
            price_df=ctx.price_df,
            trade_date=ctx.trade_date,
        )
        logger.info("Step3: 股票池 %d 只", len(ctx.universe) if ctx.universe else 0)

    # ──────────────────────────────────────────────
    # Step 4: 因子计算与预处理
    # ──────────────────────────────────────────────
    def _step4_factor_calc(self, ctx: PipelineContext) -> None:
        """计算5+1模块因子并预处理（去极值/标准化/中性化）"""
        if ctx.price_df is None or ctx.price_df.empty:
            raise ValueError("Step4: 无行情数据，无法计算因子")

        # 4a. 因子计算
        ctx.factor_df = self.factor_calculator.calculate_all(
            price_df=ctx.price_df,
            financial_df=ctx.financial_df,
            moneyflow_df=ctx.moneyflow_df,
            index_df=ctx.index_df,
            margin_df=ctx.margin_df,
            northflow_df=ctx.northflow_df,
            trade_date=ctx.trade_date,
            universe=ctx.universe,
        )

        if ctx.factor_df is not None and not ctx.factor_df.empty:
            ctx.factor_names = [c for c in ctx.factor_df.columns
                                if c not in ("ts_code", "trade_date")]
            logger.info("Step4a: 因子计算完成 %d 因子 x %d 股票",
                         len(ctx.factor_names), len(ctx.factor_df))

            # 4b. 因子预处理: 缺失值→去极值(MAD)→标准化(Z-score)→中性化
            ctx.factor_df = self.factor_preprocessor.preprocess_dataframe(
                ctx.factor_df, factor_columns=ctx.factor_names
            )
            logger.info("Step4b: 因子预处理完成")
        else:
            logger.warning("Step4: 因子计算结果为空")

    # ──────────────────────────────────────────────
    # Step 5: 信号融合
    # ──────────────────────────────────────────────
    def _step5_ensemble(self, ctx: PipelineContext) -> None:
        """动态IC加权 + Regime调权信号融合"""
        if ctx.factor_df is None or ctx.factor_df.empty:
            raise ValueError("Step5: 无因子数据，无法融合信号")

        ctx.ensemble_scores, ctx.ensemble_weights = self.ensemble_engine.combine(
            factor_df=ctx.factor_df,
            factor_names=ctx.factor_names,
            trade_date=ctx.trade_date,
        )
        logger.info("Step5: 信号融合完成, 权重数=%d",
                     len(ctx.ensemble_weights) if ctx.ensemble_weights else 0)

    # ──────────────────────────────────────────────
    # Step 6: 市场状态检测
    # ──────────────────────────────────────────────
    def _step6_regime(self, ctx: PipelineContext) -> None:
        """检测市场状态: 趋势/震荡/防御/进攻"""
        if ctx.index_df is None or ctx.index_df.empty:
            logger.warning("Step6: 无指数数据，使用默认市场状态")
            ctx.regime_state = "normal"
            ctx.regime_confidence = 0.5
            return

        ctx.regime_state, ctx.regime_confidence = self.regime_detector.detect(
            index_df=ctx.index_df,
            trade_date=ctx.trade_date,
        )
        logger.info("Step6: 市场状态=%s 置信度=%.2f", ctx.regime_state, ctx.regime_confidence)

    # ──────────────────────────────────────────────
    # Step 7: ML增强评分
    # ──────────────────────────────────────────────
    def _step7_ml_scoring(self, ctx: PipelineContext) -> None:
        """ML模型增强评分 + 自适应因子引擎"""
        if ctx.ensemble_scores is None:
            logger.warning("Step7: 无融合信号，跳过ML增强")
            ctx.final_scores = ctx.ensemble_scores
            return

        # 7a. ML模型评分
        try:
            ctx.ml_scores = self.model_scorer.predict(
                factor_df=ctx.factor_df,
                trade_date=ctx.trade_date,
            )
        except Exception as e:
            logger.warning("Step7a: ML评分失败(%s)，使用融合信号", e)
            ctx.ml_scores = None

        # 7b. 自适应因子引擎 — 更新因子画像
        try:
            self.adaptive_engine.update_profiles(
                factor_df=ctx.factor_df,
                factor_names=ctx.factor_names,
                trade_date=ctx.trade_date,
            )
        except Exception as e:
            logger.warning("Step7b: 自适应引擎更新失败: %s", e)

        # 7c. 融合ML评分与Ensemble评分
        if ctx.ml_scores is not None and not ctx.ml_scores.empty:
            # ML权重根据regime调整: 防御状态下降低ML权重
            ml_weight = 0.3
            if ctx.regime_state in ("defensive", "crisis"):
                ml_weight = 0.15
            elif ctx.regime_state in ("aggressive", "trending"):
                ml_weight = 0.4

            # 对齐索引
            common_idx = ctx.ensemble_scores.index.intersection(ctx.ml_scores.index)
            ctx.final_scores = (
                (1 - ml_weight) * ctx.ensemble_scores.loc[common_idx]
                + ml_weight * ctx.ml_scores.loc[common_idx]
            )
            logger.info("Step7: ML增强完成 (ml_weight=%.2f, n=%d)", ml_weight, len(common_idx))
        else:
            ctx.final_scores = ctx.ensemble_scores
            logger.info("Step7: 使用纯Ensemble信号 (n=%d)", len(ctx.final_scores))

    # ──────────────────────────────────────────────
    # Step 8: 组合构建与优化
    # ──────────────────────────────────────────────
    def _step8_portfolio(self, ctx: PipelineContext) -> None:
        """构建组合 + 优化权重"""
        if ctx.final_scores is None or ctx.final_scores.empty:
            raise ValueError("Step8: 无评分数据，无法构建组合")

        # 8a. 初始组合构建
        ctx.portfolio_stocks = self.portfolio_builder.build(
            scores=ctx.final_scores,
            universe=ctx.universe,
            regime_state=ctx.regime_state,
            trade_date=ctx.trade_date,
        )

        # 8b. 组合权重优化
        if ctx.factor_df is not None and not ctx.factor_df.empty:
            ctx.portfolio_weights = self.portfolio_optimizer.optimize(
                factor_df=ctx.factor_df,
                scores=ctx.final_scores,
                selected_stocks=ctx.portfolio_stocks,
                regime_state=ctx.regime_state,
            )
        else:
            # 等权fallback
            n = len(ctx.portfolio_stocks)
            ctx.portfolio_weights = pd.Series(
                1.0 / n, index=ctx.portfolio_stocks
            ) if n > 0 else pd.Series(dtype=float)

        logger.info("Step8: 组合构建完成 %d 只股票", len(ctx.portfolio_stocks))

    # ──────────────────────────────────────────────
    # Step 9: 风险预算与择时
    # ──────────────────────────────────────────────
    def _step9_risk_timing(self, ctx: PipelineContext) -> None:
        """风险预算分配 + 市场择时信号"""
        # 9a. 风险预算
        if ctx.portfolio_weights is not None and not ctx.portfolio_weights.empty:
            try:
                ctx.risk_budget = self.risk_budget_engine.allocate(
                    weights=ctx.portfolio_weights,
                    factor_df=ctx.factor_df,
                    regime_state=ctx.regime_state,
                )
            except Exception as e:
                logger.warning("Step9a: 风险预算分配失败: %s", e)

        # 9b. 市场择时
        if ctx.index_df is not None and not ctx.index_df.empty:
            try:
                ctx.timing_signal, ctx.position_ratio = self.market_timer.get_signal(
                    index_df=ctx.index_df,
                    trade_date=ctx.trade_date,
                    regime_state=ctx.regime_state,
                )
            except Exception as e:
                logger.warning("Step9b: 择时信号失败: %s", e)
                ctx.timing_signal = "hold"
                ctx.position_ratio = 1.0

        # 9c. 根据择时信号调整仓位
        if ctx.portfolio_weights is not None and ctx.position_ratio != 1.0:
            ctx.portfolio_weights = ctx.portfolio_weights * ctx.position_ratio
            logger.info("Step9: 仓位调整 ratio=%.2f signal=%s", ctx.position_ratio, ctx.timing_signal)
        else:
            logger.info("Step9: 风险预算与择时完成")

    # ──────────────────────────────────────────────
    # Step 10: 回测验证
    # ──────────────────────────────────────────────
    def _step10_backtest(self, ctx: PipelineContext) -> None:
        """对当前组合做快速回测验证"""
        if ctx.price_df is None or ctx.price_df.empty:
            logger.warning("Step10: 无行情数据，跳过回测验证")
            return

        try:
            ctx.backtest_result = self.backtest_engine.run(
                price_df=ctx.price_df,
                portfolio_weights=ctx.portfolio_weights,
                trade_date=ctx.trade_date,
                universe=ctx.universe,
            )
            if ctx.backtest_result:
                metrics = ctx.backtest_result.get("metrics", {})
                logger.info("Step10: 回测完成 sharpe=%.2f max_dd=%.2f%%",
                             metrics.get("sharpe_ratio", 0),
                             metrics.get("max_drawdown", 0) * 100)
        except Exception as e:
            logger.warning("Step10: 回测验证失败: %s", e)

    # ──────────────────────────────────────────────
    # Step 11: 因子健康检查
    # ──────────────────────────────────────────────
    def _step11_factor_health(self, ctx: PipelineContext) -> None:
        """因子衰减与漂移监控: IC漂移/PSI/KS"""
        if ctx.factor_df is None or ctx.factor_df.empty:
            logger.warning("Step11: 无因子数据，跳过健康检查")
            return

        try:
            ctx.factor_health = self.factor_monitor.check_all_modules(
                factor_df=ctx.factor_df,
                factor_names=ctx.factor_names,
                trade_date=ctx.trade_date,
            )
            if ctx.factor_health:
                unhealthy = [k for k, v in ctx.factor_health.items()
                             if v.get("status") == "unhealthy"]
                if unhealthy:
                    logger.warning("Step11: 不健康因子: %s", unhealthy)
                else:
                    logger.info("Step11: 所有因子健康")
        except Exception as e:
            logger.warning("Step11: 因子健康检查失败: %s", e)

    # ──────────────────────────────────────────────
    # Step 12: 结果存档
    # ──────────────────────────────────────────────
    def _step12_archive(self, ctx: PipelineContext) -> None:
        """保存组合/因子/监控结果到数据库和文件"""
        archive_dir = Path("data/archive") / ctx.trade_date.strftime("%Y%m%d")
        archive_dir.mkdir(parents=True, exist_ok=True)

        archive_data = {
            "trade_date": str(ctx.trade_date),
            "snapshot_id": ctx.snapshot_id,
            "universe_count": len(ctx.universe) if ctx.universe else 0,
            "factor_count": len(ctx.factor_names),
            "regime_state": ctx.regime_state,
            "regime_confidence": ctx.regime_confidence,
            "timing_signal": ctx.timing_signal,
            "position_ratio": ctx.position_ratio,
            "portfolio_stocks": ctx.portfolio_stocks,
            "factor_health": ctx.factor_health,
            "ensemble_weights": ctx.ensemble_weights,
            "risk_budget": ctx.risk_budget,
        }

        # 保存组合权重
        if ctx.portfolio_weights is not None and not ctx.portfolio_weights.empty:
            archive_data["portfolio_weights"] = ctx.portfolio_weights.to_dict()

        # 保存回测结果摘要
        if ctx.backtest_result and "metrics" in ctx.backtest_result:
            archive_data["backtest_metrics"] = ctx.backtest_result["metrics"]

        # 写入JSON存档
        archive_path = archive_dir / "pipeline_result.json"
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=2, default=str)

        # 保存因子数据CSV
        if ctx.factor_df is not None and not ctx.factor_df.empty:
            ctx.factor_df.to_csv(archive_dir / "factors.csv", index=False)

        ctx.archive_path = str(archive_path)
        logger.info("Step12: 结果已存档到 %s", archive_path)

        # 尝试写入数据库
        if ctx.session is not None:
            self._save_to_db(ctx)

    def _save_to_db(self, ctx: PipelineContext) -> None:
        """将流水线结果写入数据库"""
        try:
            from app.models.strategy import Strategy
            strategy = Strategy(
                name=f"daily_pipeline_{ctx.trade_date}",
                params={
                    "snapshot_id": ctx.snapshot_id,
                    "regime_state": ctx.regime_state,
                    "timing_signal": ctx.timing_signal,
                    "position_ratio": ctx.position_ratio,
                    "portfolio_stocks": ctx.portfolio_stocks,
                    "factor_count": len(ctx.factor_names),
                    "universe_count": len(ctx.universe) if ctx.universe else 0,
                },
            )
            ctx.session.add(strategy)
            ctx.session.commit()
            logger.info("Step12: 策略结果已写入数据库")
        except Exception as e:
            logger.warning("Step12: 数据库写入失败: %s", e)
            if ctx.session:
                ctx.session.rollback()
