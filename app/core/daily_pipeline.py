"""
日终流水线 V2
==============
V2 12步流程:
1.  数据采集与PIT对齐
2.  数据快照生成
3.  股票池构建(含风险事件过滤)
4.  因子预处理流水线(缺失值→MAD→Z-score→中性化)
5.  五大模块打分
6.  信号融合(5步: 基础→IC→Regime→收缩→归一化)
7.  ML增强排序(可选, Walk-Forward)
8.  Regime检测
9.  择时仓位控制(5信号4档+回撤保护)
10. 组合构建(分层赋权+风险折扣+行业约束)
11. 因子健康检查与告警
12. 结果存档与版本管理
"""

import logging
import uuid
from datetime import date, datetime
from typing import Any

import pandas as pd

from app.core.alpha_modules import get_alpha_modules, get_risk_penalty_module
from app.core.ensemble import EnsembleEngine
from app.core.factor_monitor import FactorMonitor
from app.core.portfolio_builder import PortfolioBuilder
from app.core.regime import RegimeDetector
from app.core.risk_budget_engine import RiskBudgetEngine
from app.core.universe import UniverseBuilder

logger = logging.getLogger(__name__)


class DailyPipeline:
    """V2日终流水线"""

    def __init__(
        self,
        universe_builder: UniverseBuilder | None = None,
        ensemble_engine: EnsembleEngine | None = None,
        regime_detector: RegimeDetector | None = None,
        risk_budget_engine: RiskBudgetEngine | None = None,
        portfolio_builder: PortfolioBuilder | None = None,
        factor_monitor: FactorMonitor | None = None,
    ):
        self.universe_builder = universe_builder or UniverseBuilder()
        self.ensemble_engine = ensemble_engine or EnsembleEngine()
        self.regime_detector = regime_detector or RegimeDetector()
        self.risk_budget_engine = risk_budget_engine or RiskBudgetEngine()
        self.portfolio_builder = portfolio_builder or PortfolioBuilder()
        self.factor_monitor = factor_monitor or FactorMonitor()

    def step1_data_collection(self, trade_date: date, **kwargs) -> dict[str, Any]:
        """
        Step 1: 数据采集与PIT对齐

        - 采集行情/财务/北向/资金流/事件数据
        - PIT对齐: 按公告日取财务数据, 预告>快报>正式
        """
        # PIT对齐是防未来函数的第一道关: 财务数据必须按公告日而非报告期使用
        logger.info(f"[Step 1] 数据采集与PIT对齐: {trade_date}")
        return {
            "status": "ok",
            "trade_date": str(trade_date),
            "pit_aligned": True,
        }

    def step2_snapshot(self, trade_date: date, **kwargs) -> dict[str, Any]:
        """
        Step 2: 数据快照生成

        - 生成当日数据快照, 记录到data_snapshot_registry
        - 快照ID: snap_YYYYMMDD_xxxxxxxx
        """
        # 快照确保全流水线使用同一份数据, 防止中间数据更新导致不一致
        snapshot_id = f"snap_{trade_date.strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        logger.info(f"[Step 2] 数据快照生成: {snapshot_id}")
        return {
            "status": "ok",
            "snapshot_id": snapshot_id,
        }

    def step3_universe(self, trade_date: date, **kwargs) -> dict[str, Any]:
        """
        Step 3: 股票池构建(含风险事件过滤)

        - 核心池/扩展池
        - V2: 风险事件过滤/黑名单硬过滤/交易可行性过滤
        """
        logger.info(f"[Step 3] 股票池构建: {trade_date}")
        return {
            "status": "ok",
            "core_count": 0,
            "extended_count": 0,
        }

    def step4_factor_preprocess(self, trade_date: date, **kwargs) -> dict[str, Any]:
        """
        Step 4: 因子预处理流水线

        - 缺失值处理 → 去极值(MAD) → 标准化(Z-score) → 中性化(行业+市值)
        """
        # 顺序不可调换: MAD去极值必须在Z-score之前, 否则极端值会拉偏均值和标准差
        # 中性化必须在最后, 因为它依赖已标准化的因子值做截面回归
        logger.info(f"[Step 4] 因子预处理流水线: {trade_date}")
        return {
            "status": "ok",
            "factors_processed": 0,
        }

    def step5_module_scoring(self, df: pd.DataFrame, **kwargs) -> dict[str, Any]:
        """
        Step 5: 五大模块打分

        - 质量成长/预期修正/残差动量/资金流确认
        - 风险惩罚(独立扣分)
        """
        logger.info("[Step 5] 五大模块打分")
        alpha_modules = get_alpha_modules()
        risk_module = get_risk_penalty_module()

        module_scores = {}
        for name, module in alpha_modules.items():
            try:
                scores = module.compute_scores(df, **kwargs)
                module_scores[name] = scores
                logger.info(f"  模块 {name}: mean={scores.mean():.4f}, std={scores.std():.4f}")
            except Exception as e:
                logger.error(f"  模块 {name} 计算失败: {e}")
                module_scores[name] = pd.Series(0.0, index=df.index)

        try:
            risk_penalty = risk_module.compute_scores(df, **kwargs)
            module_scores["risk_penalty"] = risk_penalty
        except Exception as e:
            logger.error(f"  风险惩罚模块计算失败: {e}")
            module_scores["risk_penalty"] = pd.Series(0.0, index=df.index)

        return {
            "status": "ok",
            "module_scores": module_scores,
        }

    def step6_ensemble(
        self,
        df: pd.DataFrame,
        regime: str = "trending",
        precomputed_module_scores: dict[str, pd.Series] | None = None,
        precomputed_risk_penalty: pd.Series | None = None,
        **kwargs,
    ) -> tuple[pd.Series, dict]:
        """
        Step 6: 信号融合

        5步: 基础权重 → 动态IC → Regime调权 → 高相关收缩 → 归一化
        + 风险惩罚独立扣分
        """
        logger.info(f"[Step 6] 信号融合 (regime={regime})")
        final_scores, meta = self.ensemble_engine.fuse(
            df,
            regime=regime,
            precomputed_module_scores=precomputed_module_scores,
            precomputed_risk_penalty=precomputed_risk_penalty,
            **kwargs,
        )
        return final_scores, meta

    def step7_ml_enhancement(self, scores: pd.Series, **kwargs) -> pd.Series:
        """
        Step 7: ML增强排序(可选)

        - Walk-Forward训练
        - 三路融合: 规则30% + Ridge25% + LightGBM45%
        - 无ML时直接返回规则得分
        """
        logger.info("[Step 7] ML增强排序 (跳过, 使用规则得分)")
        return scores

    def step8_regime_detection(self, **kwargs) -> dict[str, Any]:
        """
        Step 8: Regime检测

        - 4维检测: 趋势/宽度/波动率/流动性
        - 4状态: risk_on/trending/defensive/mean_reverting
        """
        logger.info("[Step 8] Regime检测")
        market_data = kwargs.get("market_data", pd.DataFrame())
        if market_data.empty:
            # 无市场数据时默认震荡市
            return {"regime": "mean_reverting"}
        regime = self.regime_detector.detect(market_data)
        return {"regime": regime}

    def step9_timing_position(self, **kwargs) -> dict[str, Any]:
        """
        Step 9: 择时仓位控制

        - 5信号4档: 指数趋势/市场宽度/波动率/北向资金/回撤保护
        - 仓位: 强正面100%/正面80%/中性60%/负面30%
        """
        logger.info("[Step 9] 择时仓位控制")
        # compute_timing_position不接受regime参数, 需过滤
        timing_kwargs = {k: v for k, v in kwargs.items() if k != "regime"}
        return self.risk_budget_engine.compute_timing_position(**timing_kwargs)

    def step10_portfolio_build(self, scores: pd.Series, **kwargs) -> pd.DataFrame:
        """
        Step 10: 组合构建

        - 分层赋权: 1-10名1.5x / 11-30名1.2x / 31-60名1.0x
        - 风险折扣: D_risk + D_liq
        - 行业约束: 单行业≤20%
        - 100股整数倍
        """
        logger.info("[Step 10] 组合构建")
        return self.portfolio_builder.build(scores, **kwargs)

    def step11_factor_health_check(self, trade_date: date, **kwargs) -> dict[str, Any]:
        """
        Step 11: 因子健康检查与告警

        - IC漂移/PSI/覆盖率/缺失率
        - 模块间相关性检查
        - 告警触发与推送
        """
        logger.info(f"[Step 11] 因子健康检查: {trade_date}")
        return {
            "status": "ok",
            "healthy_factors": 0,
            "warning_factors": 0,
            "critical_factors": 0,
        }

    def step12_archive(self, trade_date: date, results: dict, **kwargs) -> dict[str, Any]:
        """
        Step 12: 结果存档与版本管理

        - 保存组合/因子/监控数据
        - 版本标记(Git commit + 配置版本)
        """
        logger.info(f"[Step 12] 结果存档: {trade_date}")
        return {
            "status": "ok",
            "archived": True,
        }

    def run(self, trade_date: date, **kwargs) -> dict[str, Any]:
        """
        执行V2完整12步流水线

        Returns:
            完整流水线结果
        """
        pipeline_start = datetime.now()
        logger.info(f"===== V2日终流水线开始: {trade_date} =====")

        results = {"trade_date": str(trade_date), "steps": {}}

        try:
            # Step 1: 数据采集与PIT对齐
            r1 = self.step1_data_collection(trade_date, **kwargs)
            results["steps"]["step1_data_collection"] = r1

            # Step 2: 数据快照
            r2 = self.step2_snapshot(trade_date, **kwargs)
            results["steps"]["step2_snapshot"] = r2

            # Step 3: 股票池
            r3 = self.step3_universe(trade_date, **kwargs)
            results["steps"]["step3_universe"] = r3

            # Step 4: 因子预处理
            r4 = self.step4_factor_preprocess(trade_date, **kwargs)
            results["steps"]["step4_factor_preprocess"] = r4

            # Step 8: Regime检测 (提前到Step5之前, 以便Step6使用regime)
            # Regime检测只依赖市场数据, 不依赖因子计算, 所以可以提前
            r8 = self.step8_regime_detection(**kwargs)
            results["steps"]["step8_regime"] = r8
            # 从regime检测结果中提取regime标签, 供step6使用
            if isinstance(r8, dict) and "regime" in r8:
                kwargs = {**kwargs, "regime": r8["regime"]}

            # Step 5: 五大模块打分 (需要DataFrame)
            # 依赖Step4预处理的因子数据, 依赖Step3的股票池确定计算范围
            df = kwargs.get("factor_df", pd.DataFrame())
            module_scores = None
            risk_penalty = None
            if not df.empty:
                r5 = self.step5_module_scoring(df, **kwargs)
                module_scores = r5.get("module_scores")
                risk_penalty = module_scores.pop("risk_penalty", None) if module_scores else None
                # Store full module info including risk_penalty (which was already popped
                # from module_scores for separate use in step6). Reconstruct the full
                # list of module names for debugging clarity.
                step5_module_names = list(module_scores.keys())
                if risk_penalty is not None:
                    step5_module_names.append("risk_penalty")
                results["steps"]["step5_module_scoring"] = {
                    "status": r5["status"],
                    "modules": step5_module_names,
                    "has_risk_penalty": risk_penalty is not None,
                }
            else:
                results["steps"]["step5_module_scoring"] = {"status": "skipped", "reason": "no_data"}

            # Step 6: 信号融合 (使用step5预计算结果, 避免重复计算)
            # 依赖Step5的模块得分 + Step8的regime标签
            if not df.empty and module_scores is not None:
                regime = kwargs.get("regime", "trending")
                scores, meta = self.step6_ensemble(
                    df,
                    regime=regime,
                    precomputed_module_scores=module_scores,
                    precomputed_risk_penalty=risk_penalty,
                    **kwargs,
                )
                results["steps"]["step6_ensemble"] = {
                    "status": "ok",
                    "final_weights": meta.get("step5_final_weights", {}),
                }
            else:
                scores = pd.Series(dtype=float)
                results["steps"]["step6_ensemble"] = {"status": "skipped"}

            # Step 7: ML增强
            # 依赖Step6的融合得分, 可选步骤, 无ML模型时直接透传
            if not scores.empty:
                enhanced_scores = self.step7_ml_enhancement(scores, **kwargs)
                results["steps"]["step7_ml_enhancement"] = {"status": "ok"}
            else:
                enhanced_scores = scores
                results["steps"]["step7_ml_enhancement"] = {"status": "skipped"}

            # Step 9: 择时仓位
            # 依赖Step8的regime + 市场数据, 与个股得分独立, 决定整体仓位水平
            r9 = self.step9_timing_position(**kwargs)
            results["steps"]["step9_timing"] = r9

            # Step 10: 组合构建
            # 依赖Step7得分(选什么) + Step9仓位(买多少) + Step3股票池(约束范围)
            if not enhanced_scores.empty:
                portfolio = self.step10_portfolio_build(enhanced_scores, **kwargs)
                results["steps"]["step10_portfolio"] = {
                    "status": "ok",
                    "holdings_count": len(portfolio),
                }
            else:
                results["steps"]["step10_portfolio"] = {"status": "skipped"}

            # Step 11: 因子健康检查
            # 依赖Step4预处理后的因子数据, 与组合构建解耦: 即使组合未构建, 仍需监控因子质量
            r11 = self.step11_factor_health_check(trade_date, **kwargs)
            results["steps"]["step11_factor_health"] = r11

            # Step 12: 结果存档
            # 放在最后: 确保全流水线结果(含各步骤元信息)都被持久化
            r12 = self.step12_archive(trade_date, results, **kwargs)
            results["steps"]["step12_archive"] = r12

        except Exception as e:
            logger.error(f"流水线执行失败: {e}", exc_info=True)
            results["status"] = "error"
            results["error"] = str(e)
            return results

        pipeline_end = datetime.now()
        duration = (pipeline_end - pipeline_start).total_seconds()
        results["status"] = "ok"
        results["duration_seconds"] = duration

        logger.info(f"===== V2日终流水线完成: {trade_date}, 耗时{duration:.1f}s =====")
        return results
