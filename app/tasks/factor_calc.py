"""
因子计算异步任务
实现ADD 6.1节步骤6: 日终因子计算 → 预处理 → 存储
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


@celery_app.task(bind=True, max_retries=3, name="app.tasks.factor_calc.run_daily_factor_calc")
def run_daily_factor_calc(self, trade_date: str | None = None):
    """
    日终因子计算任务
    流程: 获取活跃因子 → 获取行情/财务数据 → 计算因子值 → 预处理 → 存储
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        from app.core.factor_engine import FactorEngine
        from app.core.factor_preprocess import FactorPreprocessor
        from app.models.factors import Factor, FactorValue
        from app.models.market import StockDaily

        logger.info(f"Daily factor calculation started, run_id={run_id}")

        # 创建任务日志
        task_log = _create_task_log(db, "factor_calc", "日终因子计算", run_id, params={"trade_date": trade_date})

        # 确定计算日期
        if trade_date is None:
            today = datetime.now(tz=datetime.timezone.utc).date()
            # 获取最近交易日
            latest = db.query(StockDaily.trade_date).order_by(StockDaily.trade_date.desc()).first()
            calc_date = latest[0] if latest else today
        else:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date

        logger.info(f"Calculating factors for {calc_date}")

        # 获取所有活跃因子定义
        active_factors = db.query(Factor).filter(Factor.is_active).all()
        if not active_factors:
            logger.warning("No active factors found")
            _update_task_log(db, task_log, "success", result={"factors_calculated": 0})
            return {"status": "success", "factors_calculated": 0}

        # 获取当日行情数据
        stock_data = db.query(StockDaily).filter(StockDaily.trade_date == calc_date).all()

        if not stock_data:
            logger.warning(f"No stock data for {calc_date}")
            _update_task_log(db, task_log, "success", result={"factors_calculated": 0, "reason": "no_data"})
            return {"status": "success", "factors_calculated": 0, "reason": "no_data"}

        # 构建行情DataFrame
        import numpy as np
        import pandas as pd

        price_df = pd.DataFrame(
            [
                {
                    "ts_code": s.ts_code,
                    "close": s.close,
                    "open": getattr(s, "open", s.close),
                    "high": getattr(s, "high", s.close),
                    "low": getattr(s, "low", s.close),
                    "volume": getattr(s, "vol", 0),
                    "amount": getattr(s, "amount", 0),
                    "turnover_rate": getattr(s, "turnover_rate", 0),
                    "pct_chg": getattr(s, "pct_chg", 0),
                    "large_order_volume": getattr(s, "large_order_volume", 0),
                    "super_large_order_volume": getattr(s, "super_large_order_volume", 0),
                }
                for s in stock_data
            ]
        )

        # 加载补充数据

        from app.models.market import (
            IndustryDaily,
            StockAnalystConsensus,
            StockBasic,
            StockFinancial,
            StockMargin,
            StockMoneyFlow,
            StockNorthbound,
        )

        ts_codes = price_df["ts_code"].tolist()

        # 财务数据 (PIT Guard: 仅使用 ann_date <= calc_date 的已公告数据)
        financial_df = pd.DataFrame()
        try:
            from app.core.pit_guard import pit_filter_query

            fin_query = db.query(StockFinancial).filter(StockFinancial.ts_code.in_(ts_codes))
            fin_query = pit_filter_query(fin_query, StockFinancial, calc_date, db)
            fin_data = fin_query.all()
            if fin_data:
                financial_df = pd.DataFrame(
                    [
                        {
                            "ts_code": f.ts_code,
                            "ann_date": f.ann_date,
                            "end_date": f.end_date,
                            "net_profit": f.net_profit,
                            "total_equity": f.total_equity,
                            "total_assets": f.total_assets,
                            "total_equity_prev": f.total_equity_prev,
                            "total_assets_prev": f.total_assets_prev,
                            "operating_cash_flow": f.operating_cash_flow,
                            "operating_revenue": f.operating_revenue,
                            "revenue": f.operating_revenue,
                            "gross_profit": f.gross_profit,
                            "current_assets": f.current_assets,
                            "current_liabilities": f.current_liabilities,
                            "goodwill": f.goodwill,
                            "total_market_cap": f.total_market_cap,
                            "pe_ttm": f.pe_ttm,
                            "pb": f.pb,
                            "ps_ttm": f.ps_ttm,
                            "dividend_yield": f.dividend_yield,
                            "revenue_yoy": f.revenue_yoy,
                            "net_profit_yoy": f.net_profit_yoy,
                            "yoy_deduct_net_profit": f.yoy_deduct_net_profit,
                            "roe": f.roe,
                            "roa": f.roa,
                            "gross_profit_margin": f.gross_profit_margin,
                            "net_profit_margin": f.net_profit_margin,
                            "current_ratio": f.current_ratio,
                            "revenue_yoy_4q": f.revenue_yoy_4q,
                            "net_profit_yoy_4q": f.net_profit_yoy_4q,
                            "net_profit_mean_8q": f.net_profit_mean_8q,
                            "net_profit_std_8q": f.net_profit_std_8q,
                        }
                        for f in fin_data
                    ]
                )
        except Exception as e:
            logger.warning(f"财务数据加载失败: {e}")

        # 北向资金
        northbound_df = pd.DataFrame()
        try:
            nb_data = (
                db.query(StockNorthbound)
                .filter(
                    StockNorthbound.ts_code.in_(ts_codes),
                    StockNorthbound.trade_date == calc_date.strftime("%Y%m%d"),
                )
                .all()
            )
            if nb_data:
                northbound_df = pd.DataFrame(
                    [
                        {
                            "ts_code": n.ts_code,
                            "north_net_buy": n.north_net_buy,
                            "north_holding": n.north_holding,
                            "north_holding_pct": n.north_holding_pct,
                        }
                        for n in nb_data
                    ]
                )
        except Exception as e:
            logger.warning(f"北向资金加载失败: {e}")

        # 资金流向
        money_flow_df = pd.DataFrame()
        try:
            mf_data = (
                db.query(StockMoneyFlow)
                .filter(
                    StockMoneyFlow.ts_code.in_(ts_codes),
                    StockMoneyFlow.trade_date == calc_date.strftime("%Y%m%d"),
                )
                .all()
            )
            if mf_data:
                money_flow_df = pd.DataFrame(
                    [
                        {
                            "ts_code": m.ts_code,
                            "smart_net_pct": m.smart_net_pct,
                            "large_net_pct": m.large_net_pct,
                            "super_large_net_pct": m.super_large_net_pct,
                        }
                        for m in mf_data
                    ]
                )
        except Exception as e:
            logger.warning(f"资金流向加载失败: {e}")

        # 融资融券
        margin_df = pd.DataFrame()
        try:
            mg_data = (
                db.query(StockMargin)
                .filter(
                    StockMargin.ts_code.in_(ts_codes),
                    StockMargin.trade_date == calc_date.strftime("%Y%m%d"),
                )
                .all()
            )
            if mg_data:
                margin_df = pd.DataFrame(
                    [
                        {
                            "ts_code": m.ts_code,
                            "margin_balance": m.margin_balance,
                        }
                        for m in mg_data
                    ]
                )
        except Exception as e:
            logger.warning(f"融资融券加载失败: {e}")

        # 分析师一致预期
        consensus_df = pd.DataFrame()
        try:
            ac_data = (
                db.query(StockAnalystConsensus)
                .filter(
                    StockAnalystConsensus.ts_code.in_(ts_codes),
                )
                .all()
            )
            if ac_data:
                consensus_df = pd.DataFrame(
                    [
                        {
                            "ts_code": a.ts_code,
                            "effective_date": a.effective_date,
                            "consensus_eps_fy0": a.consensus_eps_fy0,
                            "consensus_eps_fy1": a.consensus_eps_fy1,
                            "analyst_coverage": a.analyst_coverage,
                            "rating_mean": a.rating_mean,
                        }
                        for a in ac_data
                    ]
                )
        except Exception as e:
            logger.warning(f"分析师数据加载失败: {e}")

        # 股票基础信息
        stock_basic_df = pd.DataFrame()
        try:
            sb_data = db.query(StockBasic).filter(StockBasic.ts_code.in_(ts_codes)).all()
            if sb_data:
                stock_basic_df = pd.DataFrame(
                    [
                        {
                            "ts_code": s.ts_code,
                            "list_date": s.list_date,
                        }
                        for s in sb_data
                    ]
                )
        except Exception as e:
            logger.warning(f"股票基础信息加载失败: {e}")

        # 行业级别数据
        industry_df = pd.DataFrame()
        try:
            id_data = db.query(IndustryDaily).filter(IndustryDaily.trade_date == calc_date).all()
            if id_data:
                industry_df = pd.DataFrame(
                    [
                        {
                            "industry_code": i.industry_code,
                            "industry_return_1m": i.industry_return_1m,
                            "industry_net_inflow": i.industry_net_inflow,
                            "industry_pe": i.industry_pe,
                            "industry_pe_mean_3y": i.industry_pe_mean_3y,
                        }
                        for i in id_data
                    ]
                )
        except Exception as e:
            logger.warning(f"行业数据加载失败: {e}")

        # 初始化因子引擎和预处理器
        engine = FactorEngine(db)
        preprocessor = FactorPreprocessor()

        total_calculated = 0
        total_stored = 0
        errors = []

        # 使用calc_all_factors一次性计算所有因子 (传入所有补充数据)
        try:
            result_df = engine.calc_all_factors(
                financial_df,
                price_df,
                northbound_df=northbound_df,
                consensus_df=consensus_df,
                money_flow_df=money_flow_df,
                margin_df=margin_df,
                stock_basic_df=stock_basic_df,
                industry_df=industry_df,
                trade_date=calc_date,
            )
        except Exception as e:
            logger.error(f"calc_all_factors失败: {e}")
            result_df = pd.DataFrame()

        if not result_df.empty:
            factor_cols = [c for c in result_df.columns if c != "security_id"]
            for factor_code in factor_cols:
                factor_def = next((f for f in active_factors if f.factor_code == factor_code), None)
                if not factor_def:
                    continue

                raw_values = result_df[factor_code].dropna()
                if raw_values.empty:
                    continue

                processed = preprocessor.preprocess(
                    raw_values,
                    fill_method="median",
                    winsorize_method="mad",
                    standardize_method="rank_normal",
                )

                records = []
                for security_id, value in processed.items():
                    sec_id = (
                        result_df.loc[security_id, "security_id"]
                        if "security_id" in result_df.columns
                        else str(security_id)
                    )
                    record = FactorValue(
                        factor_id=factor_def.id,
                        trade_date=calc_date,
                        security_id=sec_id,
                        raw_value=float(raw_values.get(security_id, np.nan))
                        if security_id in raw_values.index
                        else None,
                        processed_value=float(value),
                        zscore_value=float(value),
                        value=float(value),
                        run_id=run_id,
                    )
                    records.append(record)

                if records:
                    db.bulk_save_objects(records)
                    total_stored += len(records)
                    total_calculated += 1

        db.commit()

        # 更新任务日志
        result = {
            "trade_date": str(calc_date),
            "factors_calculated": total_calculated,
            "values_stored": total_stored,
            "errors": errors,
        }
        _update_task_log(db, task_log, "success", result=result)

        logger.info(f"Daily factor calculation completed: {total_calculated} factors, {total_stored} values stored")
        return {"status": "success", **result}

    except Exception as exc:
        logger.error(f"Factor calculation failed: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()
