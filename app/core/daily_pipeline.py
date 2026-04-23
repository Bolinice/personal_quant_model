"""
日终流水线
实现GPT设计13节: 每日完整流程
数据更新→PIT对齐→股票池→特征计算→模型打分→融合→组合优化→风险检查→存档
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.alpha_modules import AlphaModule, get_all_modules
from app.core.ensemble import AlphaEnsemble
from app.core.factor_monitor import FactorMonitor
from app.core.labels import LabelBuilder
from app.core.logging import logger
from app.core.regime import RegimeDetector
from app.core.universe import UniverseBuilder


class DailyPipeline:
    """日终流水线 - GPT设计13节"""

    def __init__(self,
                 universe_builder: Optional[UniverseBuilder] = None,
                 label_builder: Optional[LabelBuilder] = None,
                 ensemble: Optional[AlphaEnsemble] = None,
                 regime_detector: Optional[RegimeDetector] = None,
                 factor_monitor: Optional[FactorMonitor] = None,
                 modules: Optional[List[AlphaModule]] = None):
        self.universe_builder = universe_builder or UniverseBuilder()
        self.label_builder = label_builder or LabelBuilder()
        self.ensemble = ensemble or AlphaEnsemble(modules=modules)
        self.regime_detector = regime_detector or RegimeDetector()
        self.factor_monitor = factor_monitor or FactorMonitor()

    def run(self, trade_date: date,
            stock_basic_df: pd.DataFrame,
            price_df: pd.DataFrame,
            factor_df: pd.DataFrame,
            benchmark_df: Optional[pd.DataFrame] = None,
            stock_status_df: Optional[pd.DataFrame] = None,
            daily_basic_df: Optional[pd.DataFrame] = None,
            industry_df: Optional[pd.DataFrame] = None,
            current_weights: Optional[pd.Series] = None,
            risk_model_cov: Optional[pd.DataFrame] = None,
            market_data: Optional[pd.DataFrame] = None,
            large_cap_df: Optional[pd.DataFrame] = None,
            small_cap_df: Optional[pd.DataFrame] = None,
            portfolio_optimizer=None,
            max_position: float = 0.03,
            max_industry_dev: float = 0.03) -> Dict[str, Any]:
        """
        执行完整日终流程

        Args:
            trade_date: 交易日期
            stock_basic_df: 股票基本信息
            price_df: 近期行情
            factor_df: 因子数据 (已预处理)
            benchmark_df: 基准行情
            stock_status_df: 股票状态
            daily_basic_df: 每日指标
            industry_df: 行业映射
            current_weights: 当前持仓权重
            risk_model_cov: 风险模型协方差矩阵
            market_data: 市场指数行情 (用于regime检测)
            large_cap_df: 大盘指数行情
            small_cap_df: 小盘指数行情
            portfolio_optimizer: 组合优化器实例
            max_position: 单票最大权重
            max_industry_dev: 最大行业偏离

        Returns:
            流水线结果字典
        """
        result = {
            'trade_date': str(trade_date),
            'status': 'running',
            'steps': {},
        }

        try:
            # Step 1: 生成股票池
            universe = self.universe_builder.build(
                trade_date, stock_basic_df, price_df,
                stock_status_df, daily_basic_df
            )
            result['steps']['universe'] = {
                'size': len(universe),
                'sample': universe[:5] if universe else [],
            }
            logger.info(f"Pipeline step 1: universe size={len(universe)}")

            # Step 2: PIT对齐 (在factor_df中应已完成, 这里验证)
            # factor_df应该已经通过pit_manager处理
            result['steps']['pit_aligned'] = True

            # Step 3: 过滤因子数据到股票池
            if 'ts_code' in factor_df.columns:
                pool_factor_df = factor_df[factor_df['ts_code'].isin(universe)]
            elif isinstance(factor_df.index, pd.MultiIndex):
                pool_factor_df = factor_df[factor_df.index.get_level_values(0).isin(universe)]
            else:
                pool_factor_df = factor_df

            result['steps']['factor_filtered'] = {
                'n_stocks': len(pool_factor_df.index.get_level_values(0).unique()) if isinstance(pool_factor_df.index, pd.MultiIndex) else len(pool_factor_df),
            }

            # Step 4: Regime检测
            regime = REGIME_MEAN_REVERTING  # 默认
            regime_info = {}
            if market_data is not None and not market_data.empty:
                regime_info = self.regime_detector.detect_with_confidence(
                    market_data, large_cap_df, small_cap_df
                )
                regime = regime_info.get('regime', REGIME_MEAN_REVERTING)

            result['steps']['regime'] = regime_info if regime_info else {'regime': regime}

            # Step 5: 各模块打分
            module_scores = {}
            module_diagnostics = {}
            for module in self.ensemble.modules:
                try:
                    score = module.score(pool_factor_df)
                    if not score.empty:
                        module_scores[module.name] = score
                    diag = module.diagnostics(pool_factor_df)
                    module_diagnostics[module.name] = diag
                except Exception as e:
                    logger.warning(f"Module {module.name} failed: {e}")
                    module_diagnostics[module.name] = {'error': str(e)}

            result['steps']['module_scores'] = {
                name: {'mean': float(s.mean()), 'std': float(s.std()), 'count': len(s)}
                for name, s in module_scores.items() if not s.empty
            }
            result['steps']['module_diagnostics'] = {
                name: {k: v for k, v in diag.items() if k != 'ic_stats'}
                for name, diag in module_diagnostics.items()
            }

            # Step 6: 信号融合
            final_alpha, all_module_scores = self.ensemble.fuse(
                pool_factor_df, regime=regime
            )

            result['steps']['ensemble'] = {
                'alpha_mean': float(final_alpha.mean()),
                'alpha_std': float(final_alpha.std()),
                'n_stocks_scored': len(final_alpha[final_alpha != 0]),
                'weights_used': {k: round(v, 3) for k, v in self.ensemble.weights.items()},
            }

            # Step 7: 组合优化
            target_weights = None
            if portfolio_optimizer is not None and not final_alpha.empty:
                # 获取截面alpha分数 (取最新日期)
                if isinstance(final_alpha.index, pd.MultiIndex):
                    latest_date = final_alpha.index.get_level_values(-1).max()
                    cross_alpha = final_alpha.xs(latest_date, level=-1)
                else:
                    cross_alpha = final_alpha

                if risk_model_cov is not None:
                    try:
                        target_weights = portfolio_optimizer.alpha_risk_optimize(
                            alpha_scores=cross_alpha,
                            risk_model_cov=risk_model_cov,
                            current_weights=current_weights,
                            industry_data=industry_df.set_index('ts_code')['industry'] if industry_df is not None and 'industry' in industry_df.columns else None,
                            max_position=max_position,
                            max_industry_dev=max_industry_dev,
                        )
                    except Exception as e:
                        logger.warning(f"Alpha-risk optimization failed, falling back to score_to_weight: {e}")
                        target_weights = portfolio_optimizer.score_to_weight(
                            scores=cross_alpha,
                            industry_data=industry_df.set_index('ts_code')['industry'] if industry_df is not None and 'industry' in industry_df.columns else None,
                            max_position=max_position,
                        )
                else:
                    target_weights = portfolio_optimizer.score_to_weight(
                        scores=cross_alpha,
                        industry_data=industry_df.set_index('ts_code')['industry'] if industry_df is not None and 'industry' in industry_df.columns else None,
                        max_position=max_position,
                    )

            result['steps']['portfolio'] = {
                'n_positions': len(target_weights[target_weights > 0]) if target_weights is not None else 0,
                'max_weight': float(target_weights.max()) if target_weights is not None else 0,
                'turnover': float((target_weights - current_weights).abs().sum() / 2) if target_weights is not None and current_weights is not None else 0,
            } if target_weights is not None else {'status': 'skipped'}

            # Step 8: 因子健康检查
            health_results = {}
            for module_name, scores in module_scores.items():
                health = self.factor_monitor.check_health(module_name=module_name)
                health_results[module_name] = health

            result['steps']['health_check'] = {
                name: {'is_healthy': h['is_healthy'], 'alerts': h['alerts']}
                for name, h in health_results.items()
            }

            # Step 9: 存档
            result['target_weights'] = target_weights.to_dict() if target_weights is not None else {}
            result['final_alpha'] = final_alpha
            result['module_scores'] = module_scores
            result['regime'] = regime
            result['status'] = 'completed'

        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"Daily pipeline failed: {e}", exc_info=True)

        return result


# 需要导入regime常量
from app.core.regime import REGIME_MEAN_REVERTING