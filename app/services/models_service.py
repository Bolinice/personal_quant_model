from sqlalchemy.orm import Session

from app.db.base import with_db
from app.models.models import Model, ModelFactorWeight, ModelScore
from app.schemas.models import ModelCreate, ModelFactorWeightCreate, ModelUpdate


def get_factor_values(factor_id: int, trade_date: str, db: Session):
    """导入get_factor_values函数"""
    from app.services.factors_service import get_factor_values as gfvs

    return gfvs(factor_id, trade_date, db=None if db is None else db)


@with_db
def get_models(skip: int = 0, limit: int = 100, db: Session = None):
    return db.query(Model).offset(skip).limit(limit).all()


@with_db
def get_model_by_code(model_code: str, db: Session = None):
    return db.query(Model).filter(Model.model_code == model_code).first()


@with_db
def create_model(model: ModelCreate, db: Session = None):
    db_model = Model(**model.model_dump())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model


@with_db
def update_model(model_id: int, model_update: ModelUpdate, db: Session = None):
    db_model = db.query(Model).filter(Model.id == model_id).first()
    if not db_model:
        return None
    update_data = model_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_model, key, value)
    db.commit()
    db.refresh(db_model)
    return db_model


@with_db
def get_model_factor_weights(model_id: int, db: Session = None):
    return db.query(ModelFactorWeight).filter(ModelFactorWeight.model_id == model_id).all()


@with_db
def create_model_factor_weights(model_id: int, weights: list[ModelFactorWeightCreate], db: Session = None):
    db_weights = []
    for weight in weights:
        db_weight = ModelFactorWeight(model_id=model_id, factor_id=weight.factor_id, weight=weight.weight)
        db.add(db_weight)
        db_weights.append(db_weight)
    db.commit()
    for db_weight in db_weights:
        db.refresh(db_weight)
    return db_weights


@with_db
def update_model_factor_weights(model_id: int, weights: list[ModelFactorWeightCreate], db: Session = None):
    # 删除旧权重
    db.query(ModelFactorWeight).filter(ModelFactorWeight.model_id == model_id).delete()
    db.commit()

    # 添加新权重
    return create_model_factor_weights(model_id, weights, db=db)


@with_db
def get_model_scores(model_id: int, trade_date: str, selected_only: bool = False, db: Session = None):
    query = db.query(ModelScore).filter(ModelScore.model_id == model_id, ModelScore.trade_date == trade_date)
    if selected_only:
        query = query.filter(ModelScore.is_selected == True)
    return query.all()


@with_db
def create_model_scores(model_id: int, trade_date: str, scores: list, db: Session = None):
    db_scores = []
    for score in scores:
        db_score = ModelScore(
            model_id=model_id,
            trade_date=trade_date,
            security_id=score["security_id"],
            score=score.get("score"),
            rank=score.get("rank"),
            quantile=score.get("quantile"),
            is_selected=score.get("is_selected", False),
            factor_contributions=score.get("factor_contributions"),
        )
        db.add(db_score)
        db_scores.append(db_score)
    db.commit()
    for db_score in db_scores:
        db.refresh(db_score)
    return db_scores


@with_db
def calculate_model_scores(model_id: int, trade_date: str, db: Session = None):
    """计算模型评分"""
    # 获取模型配置
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        return []

    # 获取因子权重
    weights = get_model_factor_weights(model_id, db=db)
    if not weights:
        return []

    # 获取因子值
    factor_values = {}
    for weight in weights:
        factor_values[weight.factor_id] = get_factor_values(weight.factor_id, trade_date, db=db)

    # 收集所有股票ID
    all_security_ids = set()
    for fv_list in factor_values.values():
        if fv_list:
            for fv in fv_list:
                if hasattr(fv, "security_id"):
                    all_security_ids.add(fv.security_id)

    if not all_security_ids:
        return []

    # 计算评分
    scores = []
    for security_id in all_security_ids:
        total_score = 0
        contributions = {}
        for weight in weights:
            factor_value = next(
                (fv.value for fv in factor_values.get(weight.factor_id, []) if hasattr(fv, "security_id") and fv.security_id == security_id),
                0,
            )
            contribution = factor_value * weight.weight
            total_score += contribution
            contributions[weight.factor_id] = contribution

        scores.append({
            "security_id": security_id,
            "score": total_score,
            "factor_contributions": contributions,
        })

    # 按score降序排序并赋rank/quantile
    scores.sort(key=lambda x: x["score"], reverse=True)
    n = len(scores)
    for i, s in enumerate(scores):
        s["rank"] = i + 1
        s["quantile"] = int((i + 1) / n * 100)
        s["is_selected"] = s["rank"] <= max(1, n // 5)

    # 保存评分
    return create_model_scores(model_id, trade_date, scores, db=db)
