"""
风险检查异步任务（优化版）
实现ADD 6.1节步骤9: 风险检查与预警

优化点：
1. 批量查询所有模型的组合和持仓
2. 批量查询所有股票的历史数据
3. 消除N+1查询
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List

import numpy as np
import pandas as pd
from sqlalchemy import and_

from app.core.celery_config import celery_app
from app.core.logging import logger
from app.db.base import SessionLocal


def _create_task_log(db, task_type, task_name, run_id, params=None):
    """创建任务日志"""
    from app.models.task_logs import TaskLog

    log = TaskLog(
        task_type=task_type,
        task_name=task_name,
        run_id=run_id,
        status="running",
        params_json=params,
        started_at=datetime.now(tz=datetime.timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _update_task_log(db, log, status, result=None, error=None):
    """更新任务日志"""
    log.status = status
    log.ended_at = datetime.now(tz=datetime.timezone.utc)
    log.duration = (log.ended_at - log.started_at).total_seconds()
    if result:
        log.result_json = result
    if error:
        log.error_message = str(error)[:2000]
    db.commit()


@celery_app.task(bind=True, max_retries=3, name="app.tasks.risk_check_optimized.run_daily_risk_check_optimized")
def run_daily_risk_check_optimized(self, trade_date: str | None = None):
    """
    日终风险检查任务（优化版）

    优化：
    - 批量查询所有模型的组合（1次查询代替N次）
    - 批量查询所有组合的持仓（1次查询代替N次）
    - 批量查询所有股票的历史数据（1次查询代替N*M次）
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        from app.core.risk_model import RiskModel
        from app.core.batch_query import BatchQueryHelper
        from app.middleware.query_monitor import monitor_queries
        from app.models.models import Model
        from app.models.portfolios import Portfolio, PortfolioPosition
        from app.models.market.stock_daily import StockDaily

        logger.info(f"Daily risk check (optimized) started, run_id={run_id}")

        # 创建任务日志
        task_log = _create_task_log(
            db, "risk_check", "日终风险检查(优化版)", run_id, params={"trade_date": trade_date}
        )

        # 确定计算日期
        if trade_date:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
        else:
            calc_date = datetime.now(tz=datetime.timezone.utc).date()

        # 风险限制
        VAR_LIMIT = 0.02  # 日VaR限制 2%
        CVAR_LIMIT = 0.03  # 日CVaR限制 3%
        CONCENTRATION_LIMIT = 0.05  # 单股集中度限制 5%

        with monitor_queries("risk_check"):
            # 获取活跃模型
            active_models = db.query(Model).filter(Model.status == "active").all()
            if not active_models:
                _update_task_log(db, task_log, "success", result={"models_checked": 0})
                return {"status": "success", "models_checked": 0}

            model_ids = [m.id for m in active_models]
            logger.info(f"Found {len(active_models)} active models")

            # 批量查询助手
            batch_helper = BatchQueryHelper(db)

            # 批量查询所有模型的最新组合（1次查询）
            portfolios_map = batch_helper.get_portfolios_by_model_ids(model_ids)
            logger.info(f"Loaded portfolios for {len(portfolios_map)} models")

            if not portfolios_map:
                _update_task_log(db, task_log, "success", result={"models_checked": 0})
                return {"status": "success", "models_checked": 0}

            portfolio_ids = [p.id for p in portfolios_map.values()]

            # 批量查询所有组合的持仓（1次查询）
            positions_map = batch_helper.get_portfolio_positions_batch(portfolio_ids)
            logger.info(f"Loaded positions for {len(positions_map)} portfolios")

            # 收集所有需要的股票代码
            all_sec_ids = set()
            for positions in positions_map.values():
                all_sec_ids.update(p.security_id for p in positions)

            if not all_sec_ids:
                _update_task_log(db, task_log, "success", result={"models_checked": 0})
                return {"status": "success", "models_checked": 0}

            # 批量查询所有股票的历史数据（1次查询）
            lookback = 60
            end_date = calc_date
            start_date = date.fromordinal(end_date.toordinal() - lookback * 2)

            stock_history_map = batch_helper.get_stock_daily_range_batch(
                list(all_sec_ids), start_date, end_date
            )
            logger.info(f"Loaded historical data for {len(stock_history_map)} stocks")

            # 预计算所有股票的收益率序列
            stock_returns_map: Dict[str, pd.Series] = {}
            for sec_id, daily_data in stock_history_map.items():
                if daily_data:
                    returns = pd.Series(
                        [getattr(d, "pct_chg", 0) / 100 for d in daily_data],
                        index=[d.trade_date for d in daily_data],
                    )
                    stock_returns_map[sec_id] = returns

            risk_model = RiskModel()
            total_checked = 0
            alerts = []

            # 处理每个模型
            for model in active_models:
                try:
                    # 从批量查询结果中获取组合
                    portfolio = portfolios_map.get(model.id)
                    if not portfolio:
                        continue

                    # 从批量查询结果中获取持仓
                    positions = positions_map.get(portfolio.id, [])
                    if not positions:
                        continue

                    # 构建权重向量
                    weights = np.array([p.target_weight for p in positions])
                    sec_ids = [p.security_id for p in positions]

                    # === 1. 集中度检查 ===
                    max_weight = weights.max() if len(weights) > 0 else 0
                    if max_weight > CONCENTRATION_LIMIT:
                        alerts.append({
                            "model_id": model.id,
                            "model_code": model.model_code,
                            "alert_type": "concentration",
                            "severity": "high",
                            "message": f"单股集中度 {max_weight:.2%} 超过限制 {CONCENTRATION_LIMIT:.2%}",
                            "value": float(max_weight),
                            "limit": CONCENTRATION_LIMIT,
                        })

                    # === 2. VaR/CVaR检查 ===
                    # 从预计算的收益率中获取数据
                    stock_returns = {
                        sec_id: stock_returns_map[sec_id]
                        for sec_id in sec_ids
                        if sec_id in stock_returns_map
                    }

                    if stock_returns:
                        # 构建收益率矩阵
                        returns_df = pd.DataFrame(stock_returns)
                        returns_df = returns_df.fillna(0)

                        # 组合收益率
                        aligned_weights = np.array([
                            weights[i] for i, sid in enumerate(sec_ids)
                            if sid in returns_df.columns
                        ])
                        aligned_returns = returns_df[[
                            sid for sid in sec_ids if sid in returns_df.columns
                        ]]

                        if len(aligned_weights) > 0 and len(aligned_returns) > 20:
                            portfolio_returns = aligned_returns.values @ aligned_weights
                            port_ret_series = pd.Series(portfolio_returns)

                            # 计算VaR
                            var_95 = risk_model.historical_var(port_ret_series, confidence=0.95)
                            cvar_95 = risk_model.conditional_var(port_ret_series, confidence=0.95)

                            # VaR检查
                            if abs(var_95) > VAR_LIMIT:
                                alerts.append({
                                    "model_id": model.id,
                                    "model_code": model.model_code,
                                    "alert_type": "var",
                                    "severity": "medium",
                                    "message": f"VaR(95%) {abs(var_95):.2%} 超过限制 {VAR_LIMIT:.2%}",
                                    "value": float(abs(var_95)),
                                    "limit": VAR_LIMIT,
                                })

                            # CVaR检查
                            if abs(cvar_95) > CVAR_LIMIT:
                                alerts.append({
                                    "model_id": model.id,
                                    "model_code": model.model_code,
                                    "alert_type": "cvar",
                                    "severity": "high",
                                    "message": f"CVaR(95%) {abs(cvar_95):.2%} 超过限制 {CVAR_LIMIT:.2%}",
                                    "value": float(abs(cvar_95)),
                                    "limit": CVAR_LIMIT,
                                })

                    total_checked += 1
                    logger.info(f"Risk check completed for model {model.model_code}")

                except Exception as e:
                    logger.error(f"Error checking model {model.id}: {e}", exc_info=True)
                    continue

        result = {
            "models_checked": total_checked,
            "alerts_count": len(alerts),
            "alerts": alerts,
        }

        _update_task_log(db, task_log, "success", result=result)
        logger.info(f"Daily risk check completed: {result}")
        return {"status": "success", **result}

    except Exception as e:
        logger.error(f"Daily risk check failed: {e}", exc_info=True)
        if "task_log" in locals():
            _update_task_log(db, task_log, "failed", error=str(e))
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()
