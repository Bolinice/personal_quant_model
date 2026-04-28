"""
模型打分异步任务
实现ADD 6.1节步骤7-8: 日终模型评分 → 组合生成
"""

from __future__ import annotations

from datetime import date, datetime

from app.core.celery_config import celery_app
from app.core.logging import logger
from app.db.base import SessionLocal
import contextlib


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


@celery_app.task(bind=True, max_retries=3, name="app.tasks.model_score.run_daily_model_score")
def run_daily_model_score(self, trade_date: str | None = None):
    """
    日终模型打分任务
    流程: 获取活跃模型 → 获取因子权重 → 获取因子值 → 计算综合评分 → 存储
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        import pandas as pd
        from sqlalchemy import and_

        from app.core.factor_preprocess import preprocess_factor_values
        from app.core.model_scorer import MultiFactorScorer
        from app.models.factors import Factor, FactorValue
        from app.models.models import Model, ModelFactorWeight, ModelPerformance, ModelScore

        logger.info(f"Daily model scoring started, run_id={run_id}")

        # 创建任务日志
        task_log = _create_task_log(db, "model_score", "日终模型打分", run_id, params={"trade_date": trade_date})

        # 确定计算日期
        if trade_date:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
        else:
            calc_date = date.today()

        # 获取所有活跃模型
        active_models = db.query(Model).filter(Model.status == "active").all()
        if not active_models:
            logger.warning("No active models found")
            _update_task_log(db, task_log, "success", result={"models_scored": 0})
            return {"status": "success", "models_scored": 0}

        scorer = MultiFactorScorer(db)
        total_scored = 0
        total_stocks = 0
        errors = []

        for model in active_models:
            try:
                logger.info(f"Scoring model: {model.model_code} (id={model.id})")

                # 获取模型因子权重
                weights = (
                    db.query(ModelFactorWeight)
                    .filter(
                        ModelFactorWeight.model_id == model.id,
                        ModelFactorWeight.is_active,
                    )
                    .all()
                )

                if not weights:
                    logger.warning(f"No factor weights for model {model.id}")
                    continue

                # 获取因子值并构建得分矩阵
                factor_scores = {}
                factor_codes = {}

                for fw in weights:
                    factor = db.query(Factor).filter(Factor.id == fw.factor_id).first()
                    if not factor:
                        continue

                    # 查询因子值
                    values = (
                        db.query(FactorValue)
                        .filter(
                            and_(
                                FactorValue.factor_id == fw.factor_id,
                                FactorValue.trade_date == calc_date,
                            )
                        )
                        .all()
                    )

                    if not values:
                        continue

                    series = pd.Series({v.security_id: v.value for v in values})

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
                    model.model_config.get("weighting_method", "equal") if model.model_config else "equal"
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

                # 批量写入评分结果
                records = []
                for security_id, row in scores_df.iterrows():
                    record = ModelScore(
                        model_id=model.id,
                        trade_date=calc_date,
                        security_id=str(security_id),
                        score=float(row.get("total_score", 0)),
                        rank=int(row.get("rank", 0)),
                        quantile=int(row.get("quantile", 0) * 100),
                        is_selected=bool(row.get("is_selected", False)),
                    )
                    records.append(record)

                if records:
                    db.bulk_save_objects(records)
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
                logger.info(f"Model {model.model_code}: scored {len(scores_df)} stocks, selected {len(selected)}")

            except Exception as e:
                error_msg = f"Model {model.id} scoring failed: {e!s}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

        # 更新任务日志
        result = {
            "trade_date": str(calc_date),
            "models_scored": total_scored,
            "total_stocks": total_stocks,
            "errors": errors,
        }
        _update_task_log(db, task_log, "success", result=result)

        logger.info(f"Daily model scoring completed: {total_scored} models, {total_stocks} stocks scored")
        return {"status": "success", **result}

    except Exception as exc:
        logger.error(f"Model scoring failed: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
