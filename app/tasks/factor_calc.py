"""
因子计算异步任务
实现ADD 6.1节步骤6: 日终因子计算 → 预处理 → 存储
"""
from datetime import datetime, date
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
        started_at=datetime.now(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _update_task_log(db, log, status, result=None, error=None):
    """更新任务日志"""
    log.status = status
    log.ended_at = datetime.now()
    log.duration = (log.ended_at - log.started_at).total_seconds()
    if result:
        log.result_json = result
    if error:
        log.error_message = str(error)[:2000]
    db.commit()


@celery_app.task(bind=True, max_retries=3, name="app.tasks.factor_calc.run_daily_factor_calc")
def run_daily_factor_calc(self, trade_date: str = None):
    """
    日终因子计算任务
    流程: 获取活跃因子 → 获取行情/财务数据 → 计算因子值 → 预处理 → 存储
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        from app.models.factors import Factor, FactorValue
        from app.models.market import StockDaily
        from app.core.factor_engine import FactorEngine, FACTOR_GROUPS
        from app.core.factor_preprocess import FactorPreprocessor
        from sqlalchemy import and_

        logger.info(f"Daily factor calculation started, run_id={run_id}")

        # 创建任务日志
        task_log = _create_task_log(db, "factor_calc", "日终因子计算", run_id,
                                     params={"trade_date": trade_date})

        # 确定计算日期
        if trade_date is None:
            today = date.today()
            # 获取最近交易日
            latest = db.query(StockDaily.trade_date).order_by(
                StockDaily.trade_date.desc()
            ).first()
            calc_date = latest[0] if latest else today
        else:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date

        logger.info(f"Calculating factors for {calc_date}")

        # 获取所有活跃因子定义
        active_factors = db.query(Factor).filter(Factor.is_active == True).all()
        if not active_factors:
            logger.warning("No active factors found")
            _update_task_log(db, task_log, "success", result={"factors_calculated": 0})
            return {"status": "success", "factors_calculated": 0}

        # 获取当日行情数据
        stock_data = db.query(StockDaily).filter(
            StockDaily.trade_date == calc_date
        ).all()

        if not stock_data:
            logger.warning(f"No stock data for {calc_date}")
            _update_task_log(db, task_log, "success", result={"factors_calculated": 0, "reason": "no_data"})
            return {"status": "success", "factors_calculated": 0, "reason": "no_data"}

        # 构建行情DataFrame
        import pandas as pd
        import numpy as np

        price_df = pd.DataFrame([{
            'ts_code': s.ts_code,
            'close': s.close,
            'open': getattr(s, 'open', s.close),
            'high': getattr(s, 'high', s.close),
            'low': getattr(s, 'low', s.close),
            'volume': getattr(s, 'vol', 0),
            'amount': getattr(s, 'amount', 0),
            'turnover_rate': getattr(s, 'turnover_rate', 0),
            'pct_chg': getattr(s, 'pct_chg', 0),
        } for s in stock_data])

        # 初始化因子引擎和预处理器
        engine = FactorEngine(db)
        preprocessor = FactorPreprocessor()

        total_calculated = 0
        total_stored = 0
        errors = []

        # 按因子组计算
        for group_code, group_info in FACTOR_GROUPS.items():
            try:
                # 只计算该组中已注册的活跃因子
                group_factor_codes = group_info['factors']
                registered_codes = {f.factor_code for f in active_factors}
                codes_to_calc = [c for c in group_factor_codes if c in registered_codes]

                if not codes_to_calc:
                    continue

                # 根据因子组选择计算方法
                if group_code == 'valuation':
                    # 价值因子需要财务数据，从行情中提取可用字段
                    financial_df = price_df.copy()
                    financial_df['pe_ttm'] = np.nan  # 需要从财务数据源获取
                    financial_df['pb'] = np.nan
                    financial_df['ps_ttm'] = np.nan
                    result_df = engine.calc_valuation_factors(financial_df, price_df)
                elif group_code == 'growth':
                    financial_df = price_df.copy()
                    result_df = engine.calc_growth_factors(financial_df)
                elif group_code == 'quality':
                    financial_df = price_df.copy()
                    result_df = engine.calc_quality_factors(financial_df)
                elif group_code == 'momentum':
                    result_df = engine.calc_momentum_factors(price_df)
                elif group_code == 'volatility':
                    result_df = engine.calc_volatility_factors(price_df)
                elif group_code == 'liquidity':
                    result_df = engine.calc_liquidity_factors(price_df)
                elif group_code == 'microstructure':
                    result_df = engine.calc_microstructure_factors(price_df)
                else:
                    # 其他因子组(北向/分析师/政策等)需要外部数据源
                    # 跳过，由专门的数据同步任务提供
                    continue

                if result_df.empty:
                    continue

                # 存储因子值
                for factor_code in codes_to_calc:
                    if factor_code not in result_df.columns:
                        continue

                    factor_def = next((f for f in active_factors if f.factor_code == factor_code), None)
                    if not factor_def:
                        continue

                    # 预处理
                    raw_values = result_df[factor_code].dropna()
                    if raw_values.empty:
                        continue

                    processed = preprocessor.preprocess(
                        raw_values,
                        fill_method='median',
                        winsorize_method='mad',
                        standardize_method='rank_normal',
                    )

                    # 批量写入
                    records = []
                    for security_id, value in processed.items():
                        sec_id = result_df.loc[security_id, 'security_id'] if 'security_id' in result_df.columns else str(security_id)
                        record = FactorValue(
                            factor_id=factor_def.id,
                            trade_date=calc_date,
                            security_id=sec_id,
                            raw_value=float(raw_values.get(security_id, np.nan)) if security_id in raw_values.index else None,
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

            except Exception as e:
                error_msg = f"Factor group {group_code} failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

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
        try:
            _update_task_log(db, task_log, "failed", error=exc)
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
