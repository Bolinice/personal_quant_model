"""
模型打分异步任务（优化版）
实现ADD 6.1节步骤7-8: 日终模型评分 → 组合生成

优化点：
1. 批量查询因子定义和因子值，消除N+1查询
2. 使用 bulk_insert_mappings 替代 bulk_save_objects
3. 添加查询监控
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime
from typing import Dict, List

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


@celery_app.task(bind=True, max_retries=3, name="app.tasks.model_score_optimized.run_daily_model_score_optimized")
def run_daily_model_score_optimized(self, trade_date: str | None = None):
    """
    日终模型打分任务（优化版）

    优化：
    - 批量查询所有模型的因子权重（1次查询代替N次）
    - 批量查询所有因子定义（1次查询代替N*M次）
    - 批量查询所有因子值（1次查询代替N*M次）
    - 使用 bulk_insert_mappings 批量插入
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        import pandas as pd
        from sqlalchemy import and_

        from app.core.factor_preprocess import preprocess_factor_values
        from app.core.model_scorer import MultiFactorScorer
        from app.core.batch_query import BatchQueryHelper
        from app.middleware.query_monitor import monitor_queries
        from app.models.factors import Factor, FactorValue
        from app.models.models import Model, ModelFactorWeight, ModelPerformance, ModelScore

        logger.info(f"Daily model scoring (optimized) started, run_id={run_id}")

        # 创建任务日志
        task_log = _create_task_log(
            db, "model_score", "日终模型打分(优化版)", run_id, params={"trade_date": trade_date}
        )

        # 确定计算日期
        if trade_date:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
        else:
            calc_date = datetime.now(tz=datetime.timezone.utc).date()

        with monitor_queries("model_scoring"):
            # 获取所有活跃模型
            active_models = db.query(Model).filter(Model.status == "active").all()
            if not active_models:
                logger.warning("No active models found")
                _update_task_log(db, task_log, "success", result={"models_scored": 0})
                return {"status": "success", "models_scored": 0}

            model_ids = [m.id for m in active_models]
            logger.info(f"Found {len(active_models)} active models")

            # 批量查询助手
            batch_helper = BatchQueryHelper(db)

            # 批量查询所有模型的因子权重（1次查询）
            model_weights_map = batch_helper.get_model_factor_weights_batch(model_ids)
            logger.info(f"Loaded factor weights for {len(model_weights_map)} models")

            # 收集所有需要的因子ID
            all_factor_ids = set()
            for weights in model_weights_map.values():
                all_factor_ids.update(fw.factor_id for fw in weights)

            if not all_factor_ids:
                logger.warning("No factor weights found for any model")
                _update_task_log(db, task_log, "success", result={"models_scored": 0})
                return {"status": "success", "models_scored": 0}

            # 批量查询所有因子定义（1次查询）
            factors_map = batch_helper.get_factors_by_ids(list(all_factor_ids))
            logger.info(f"Loaded {len(factors_map)} factor definitions")

            # 批量查询所有因子值（1次查询）
            factor_values_map = batch_helper.get_factor_values_batch(
                list(all_factor_ids), calc_date
            )
            logger.info(f"Loaded factor values for {len(factor_values_map)} factors")

            scorer = MultiFactorScorer(db)
            total_scored = 0
            total_stocks = 0
            errors = []

            # 处理每个模型
            for model in active_models:
                try:
                    logger.info(f"Scoring model: {model.model_code} (id={model.id})")

                    # 从批量查询结果中获取权重
                    weights = model_weights_map.get(model.id, [])
                    if not weights:
                        logger.warning(f"No factor weights for model {model.id}")
                        continue

                    # 构建因子得分矩阵
                    factor_scores = {}
                    factor_codes = {}

                    for fw in weights:
                        # 从批量查询结果中获取因子定义
                        factor = factors_map.get(fw.factor_id)
                        if not factor:
                            continue

                        # 从批量查询结果中获取因子值
                        values_dict = factor_values_map.get(fw.factor_id, {})
                        if not values_dict:
                            continue

                        series = pd.Series(values_dict)

                        # 预处理
                        direction = fw.direction or factor.direction or 1
                        series = preprocess_factor_values(series, direction=direction)

                        factor_scores[factor.factor_code] = series
                        factor_codes[fw.factor_id] = factor.factor_code

                    if not factor_scores:
                        logger.warning(f"No factor values for model {model.id} on {calc_date}")
                        continue

                    # 构建得分矩阵
                    scores_df = pd.DataFrame(factor_scores)

                    # 获取加权方法
                    weighting_method = (
                        model.model_config.get("weighting_method", "equal")
                        if model.model_config
                        else "equal"
                    )

                    # 计算综合得分
                    if weighting_method == "equal":
                        scores_df["total_score"] = scorer.equal_weight(scores_df)
                    elif weighting_method == "manual":
                        w = {factor_codes[fw.factor_id]: fw.weight for fw in weights}
                        scores_df["total_score"] = scorer.manual_weight(scores_df, w)
                    elif weighting_method == "icir":
                        icir_vals = {factor_codes[fw.factor_id]: fw.weight for fw in weights}
                        scores_df["total_score"] = scorer.icir_weight(scores_df, icir_vals)
                    elif weighting_method == "lightgbm":
                        scores_df["total_score"] = scorer.lightgbm_score(scores_df)
                    elif weighting_method == "stacking":
                        scores_df["total_score"] = scorer.stacking_score(scores_df)
                    else:
                        scores_df["total_score"] = scorer.equal_weight(scores_df)

                    # 排名和分位
                    scores_df["rank"] = scores_df["total_score"].rank(ascending=False)
                    scores_df["quantile"] = scores_df["total_score"].rank(pct=True)

                    # 确定入选股票
                    top_n = model.model_config.get("top_n", 50) if model.model_config else 50
                    scores_df["is_selected"] = scores_df["rank"] <= top_n

                    # 批量写入评分结果（使用 bulk_insert_mappings 更高效）
                    records = []
                    for security_id, row in scores_df.iterrows():
                        records.append({
                            "model_id": model.id,
                            "trade_date": calc_date,
                            "security_id": str(security_id),
                            "score": float(row.get("total_score", 0)),
                            "rank": int(row.get("rank", 0)),
                            "quantile": int(row.get("quantile", 0) * 100),
                            "is_selected": bool(row.get("is_selected", False)),
                        })

                    if records:
                        db.bulk_insert_mappings(ModelScore, records)
                        db.commit()

                    # 更新模型表现
                    selected = scores_df[scores_df["is_selected"]]
                    perf = ModelPerformance(
                        model_id=model.id,
                        trade_date=calc_date,
                        num_selected=len(selected),
                    )
                    db.add(perf)
                    db.commit()

                    total_scored += 1
                    total_stocks += len(scores_df)
                    logger.info(
                        f"Model {model.model_code} scored: {len(scores_df)} stocks, "
                        f"{len(selected)} selected"
                    )

                except Exception as e:
                    logger.error(f"Error scoring model {model.id}: {e}", exc_info=True)
                    errors.append({"model_id": model.id, "error": str(e)})
                    continue

        result = {
            "models_scored": total_scored,
            "total_stocks": total_stocks,
            "errors": errors,
        }

        _update_task_log(db, task_log, "success", result=result)
        logger.info(f"Daily model scoring completed: {result}")
        return {"status": "success", **result}

    except Exception as e:
        logger.error(f"Daily model scoring failed: {e}", exc_info=True)
        if "task_log" in locals():
            _update_task_log(db, task_log, "failed", error=str(e))
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()
