"""
风控检查异步任务
实现ADD 6.1节步骤9-11: 日终风控检查 → 预警 → 记录
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime

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


@celery_app.task(bind=True, max_retries=3, name="app.tasks.risk_check.run_daily_risk_check")
def run_daily_risk_check(self, trade_date: str | None = None):
    """
    日终风控检查任务
    流程: 获取活跃模型组合 → 计算风险指标 → 检查风控约束 → 生成预警 → 记录
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        import numpy as np
        import pandas as pd

        from app.core.risk_model import RiskModel
        from app.models.market import StockDaily
        from app.models.models import Model
        from app.models.portfolios import Portfolio, PortfolioPosition

        logger.info(f"Daily risk check started, run_id={run_id}")

        # 创建任务日志
        task_log = _create_task_log(db, "risk_check", "日终风控检查", run_id, params={"trade_date": trade_date})

        # 确定计算日期
        if trade_date:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
        else:
            calc_date = datetime.now(tz=datetime.timezone.utc).date()

        risk_model = RiskModel()

        # 风控参数
        MAX_DRAWDOWN_LIMIT = 0.10  # 最大回撤限制 10%
        VAR_LIMIT = 0.02  # 日VaR限制 2%
        CVAR_LIMIT = 0.03  # 日CVaR限制 3%
        CONCENTRATION_LIMIT = 0.05  # 单股集中度限制 5%
        _INDUSTRY_CONCENTRATION = 0.30  # 行业集中度限制 30%
        _TURNOVER_LIMIT = 0.30  # 换手率限制 30%

        # 获取活跃模型
        active_models = db.query(Model).filter(Model.status == "active").all()
        if not active_models:
            _update_task_log(db, task_log, "success", result={"models_checked": 0})
            return {"status": "success", "models_checked": 0}

        total_checked = 0
        alerts = []

        for model in active_models:
            try:
                # 获取最新组合
                portfolio = (
                    db.query(Portfolio)
                    .filter(
                        Portfolio.model_id == model.id,
                    )
                    .order_by(Portfolio.trade_date.desc())
                    .first()
                )

                if not portfolio:
                    continue

                # 获取持仓
                positions = db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio.id).all()

                if not positions:
                    continue

                # 构建权重向量
                weights = np.array([p.target_weight for p in positions])
                sec_ids = [p.security_id for p in positions]

                # === 1. 集中度检查 ===
                max_weight = weights.max() if len(weights) > 0 else 0
                if max_weight > CONCENTRATION_LIMIT:
                    alerts.append(
                        {
                            "model_id": model.id,
                            "model_code": model.model_code,
                            "alert_type": "concentration",
                            "severity": "high",
                            "message": f"单股集中度 {max_weight:.2%} 超过限制 {CONCENTRATION_LIMIT:.2%}",
                            "value": float(max_weight),
                            "limit": CONCENTRATION_LIMIT,
                        }
                    )

                # === 2. VaR/CVaR检查 ===
                # 获取近60日收益率数据
                lookback = 60
                end_date = calc_date
                start_date = date.fromordinal(end_date.toordinal() - lookback * 2)

                # 获取组合中股票的历史收益率
                stock_returns = {}
                for sec_id in sec_ids:
                    daily_data = (
                        db.query(StockDaily)
                        .filter(
                            StockDaily.ts_code == sec_id,
                            StockDaily.trade_date >= start_date,
                            StockDaily.trade_date <= end_date,
                        )
                        .order_by(StockDaily.trade_date)
                        .all()
                    )

                    if daily_data:
                        returns = pd.Series(
                            [getattr(d, "pct_chg", 0) / 100 for d in daily_data],
                            index=[d.trade_date for d in daily_data],
                        )
                        stock_returns[sec_id] = returns

                if stock_returns:
                    # 构建收益率矩阵
                    returns_df = pd.DataFrame(stock_returns)
                    returns_df = returns_df.fillna(0)

                    # 组合收益率
                    aligned_weights = np.array(
                        [weights[i] for i, sid in enumerate(sec_ids) if sid in returns_df.columns]
                    )
                    aligned_returns = returns_df[[sid for sid in sec_ids if sid in returns_df.columns]]

                    if len(aligned_weights) > 0 and len(aligned_returns) > 20:
                        portfolio_returns = aligned_returns.values @ aligned_weights
                        port_ret_series = pd.Series(portfolio_returns)

                        # 计算VaR
                        var_95 = risk_model.historical_var(port_ret_series, confidence=0.95)
                        cvar_95 = risk_model.conditional_var(port_ret_series, confidence=0.95)
                        _student_t_var = risk_model.student_t_var(port_ret_series, confidence=0.95)

                        if var_95 > VAR_LIMIT:
                            alerts.append(
                                {
                                    "model_id": model.id,
                                    "model_code": model.model_code,
                                    "alert_type": "var_breach",
                                    "severity": "high",
                                    "message": f"日VaR {var_95:.2%} 超过限制 {VAR_LIMIT:.2%}",
                                    "value": float(var_95),
                                    "limit": VAR_LIMIT,
                                }
                            )

                        if cvar_95 > CVAR_LIMIT:
                            alerts.append(
                                {
                                    "model_id": model.id,
                                    "model_code": model.model_code,
                                    "alert_type": "cvar_breach",
                                    "severity": "critical",
                                    "message": f"日CVaR {cvar_95:.2%} 超过限制 {CVAR_LIMIT:.2%}",
                                    "value": float(cvar_95),
                                    "limit": CVAR_LIMIT,
                                }
                            )

                        # === 3. 回撤检查 ===
                        cum_nav = (1 + port_ret_series).cumprod()
                        cummax = cum_nav.cummax()
                        drawdown = ((cum_nav - cummax) / cummax).min()

                        if drawdown < -MAX_DRAWDOWN_LIMIT:
                            alerts.append(
                                {
                                    "model_id": model.id,
                                    "model_code": model.model_code,
                                    "alert_type": "drawdown_breach",
                                    "severity": "critical",
                                    "message": f"最大回撤 {drawdown:.2%} 超过限制 -{MAX_DRAWDOWN_LIMIT:.2%}",
                                    "value": float(drawdown),
                                    "limit": -MAX_DRAWDOWN_LIMIT,
                                }
                            )

                        # === 4. 协方差矩阵正定性检查 ===
                        if len(aligned_returns.columns) >= 2 and len(aligned_returns) > len(aligned_returns.columns):
                            try:
                                cov = risk_model.ledoit_wolf_shrinkage(aligned_returns)
                                eigvals = np.linalg.eigvals(cov.values)
                                min_eigval = eigvals.min()
                                if min_eigval < 1e-8:
                                    alerts.append(
                                        {
                                            "model_id": model.id,
                                            "model_code": model.model_code,
                                            "alert_type": "cov_not_positive_definite",
                                            "severity": "medium",
                                            "message": f"协方差矩阵最小特征值 {min_eigval:.2e} 接近0",
                                            "value": float(min_eigval),
                                        }
                                    )
                            except Exception:
                                pass

                total_checked += 1
                logger.info(
                    f"Model {model.model_code}: risk check completed, alerts={len([a for a in alerts if a.get('model_id') == model.id])}"
                )

            except Exception as e:
                logger.error(f"Risk check for model {model.id} failed: {e}")
                alerts.append(
                    {
                        "model_id": model.id,
                        "model_code": model.model_code,
                        "alert_type": "check_error",
                        "severity": "high",
                        "message": f"风控检查异常: {str(e)[:200]}",
                    }
                )
                continue

        # 汇总结果
        critical_alerts = [a for a in alerts if a.get("severity") == "critical"]
        high_alerts = [a for a in alerts if a.get("severity") == "high"]
        medium_alerts = [a for a in alerts if a.get("severity") == "medium"]

        result = {
            "trade_date": str(calc_date),
            "models_checked": total_checked,
            "total_alerts": len(alerts),
            "critical_alerts": len(critical_alerts),
            "high_alerts": len(high_alerts),
            "medium_alerts": len(medium_alerts),
            "alerts": alerts,
        }
        _update_task_log(db, task_log, "success", result=result)

        # 如果有critical级别预警，记录日志
        if critical_alerts:
            logger.critical(f"CRITICAL risk alerts: {len(critical_alerts)} alerts require immediate attention!")

        logger.info(f"Daily risk check completed: {total_checked} models, {len(alerts)} alerts")
        return {"status": "success", **result}

    except Exception as exc:
        logger.error(f"Risk check failed: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()
