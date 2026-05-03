"""模型管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.models.models import Model, ModelPerformance
from app.schemas.models import ModelCreate, ModelFactorWeightCreate, ModelUpdate
from app.services.models_service import (
    calculate_model_scores,
    create_model,
    create_model_factor_weights,
    get_model_factor_weights,
    get_model_scores,
    get_models,
    update_model,
    update_model_factor_weights,
)

router = APIRouter()


@router.get("/templates")
def read_template_models(db: Session = Depends(get_db)):
    """获取模板策略列表（包含回测结果）"""
    from app.models.backtests import Backtest, BacktestResult

    # 查询所有模板策略
    models = db.query(Model).filter(Model.model_code.like('TEMPLATE_%')).order_by(Model.id).all()

    result = []
    for model in models:
        # 获取该模型的回测记录
        backtest = db.query(Backtest).filter_by(model_id=model.id).first()
        backtest_result = None

        if backtest:
            # 获取回测结果
            br = db.query(BacktestResult).filter_by(backtest_id=backtest.id).first()
            if br:
                backtest_result = {
                    'backtest_id': backtest.id,
                    'start_date': backtest.start_date.isoformat(),
                    'end_date': backtest.end_date.isoformat(),
                    'total_return': br.total_return,
                    'annual_return': br.annual_return,
                    'sharpe': br.sharpe,
                    'max_drawdown': br.max_drawdown,
                    'calmar': br.calmar,
                    'information_ratio': br.information_ratio,
                    'win_rate': br.win_rate,
                }

        result.append({
            'id': model.id,
            'model_name': model.model_name,
            'model_code': model.model_code,
            'description': model.description,
            'status': model.status,
            'backtest_result': backtest_result,
        })

    return success(result)


@router.get("/")
def read_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取模型列表"""
    models = get_models(skip=skip, limit=limit, db=db)
    return success(models)


@router.get("/{model_id}")
def read_model(model_id: int, db: Session = Depends(get_db)):
    """获取模型详情"""
    model = db.query(Model).filter(Model.id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return success(model)


@router.post("/")
def create_model_endpoint(model: ModelCreate, db: Session = Depends(get_db)):
    """创建模型"""
    result = create_model(model, db=db)
    return success(result)


@router.put("/{model_id}")
def update_model_endpoint(model_id: int, model_update: ModelUpdate, db: Session = Depends(get_db)):
    """更新模型"""
    model = update_model(model_id, model_update, db=db)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return success(model)


@router.get("/{model_id}/factor-weights")
def read_model_factor_weights(model_id: int, db: Session = Depends(get_db)):
    """获取模型因子权重"""
    weights = get_model_factor_weights(model_id, db=db)
    return success(weights)


@router.post("/{model_id}/factor-weights")
def create_model_factor_weights_endpoint(
    model_id: int, weights: list[ModelFactorWeightCreate], db: Session = Depends(get_db)
):
    """创建模型因子权重"""
    result = create_model_factor_weights(model_id, weights, db=db)
    return success(result)


@router.put("/{model_id}/factor-weights")
def update_model_factor_weights_endpoint(
    model_id: int, weights: list[ModelFactorWeightCreate], db: Session = Depends(get_db)
):
    """更新模型因子权重"""
    result = update_model_factor_weights(model_id, weights, db=db)
    return success(result)


@router.get("/{model_id}/scores")
def read_model_scores(model_id: int, trade_date: str, selected_only: bool = False, db: Session = Depends(get_db)):
    """获取模型评分"""
    scores = get_model_scores(model_id, trade_date, selected_only, db=db)
    return success(scores)


@router.post("/{model_id}/score")
def calculate_model_scores_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    """计算模型评分"""
    result = calculate_model_scores(model_id, trade_date, db=db)
    return success(result)


@router.get("/{model_id}/performance")
def read_model_performance(model_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取模型绩效"""
    perf = (
        db.query(ModelPerformance)
        .filter(ModelPerformance.model_id == model_id)
        .order_by(ModelPerformance.trade_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return success(perf)
