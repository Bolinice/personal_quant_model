from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.models_service import get_models, get_model_by_code, create_model, update_model, get_model_factor_weights, create_model_factor_weights, update_model_factor_weights, get_model_scores, create_model_scores, calculate_model_scores
from app.models.models import Model, ModelFactorWeight, ModelScore, ModelPerformance
from app.schemas.models import ModelCreate, ModelUpdate, ModelOut, ModelFactorWeightCreate, ModelFactorWeightOut, ModelScoreCreate, ModelScoreOut, ModelPerformanceOut

router = APIRouter()

@router.get("/", response_model=List[ModelOut])
def read_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    models = get_models(skip=skip, limit=limit, db=db)
    return models

@router.get("/{model_id}", response_model=ModelOut)
def read_model(model_id: int, db: Session = Depends(get_db)):
    model = db.query(Model).filter(Model.id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@router.post("/", response_model=ModelOut)
def create_model_endpoint(model: ModelCreate, db: Session = Depends(get_db)):
    return create_model(model, db=db)

@router.put("/{model_id}", response_model=ModelOut)
def update_model_endpoint(model_id: int, model_update: ModelUpdate, db: Session = Depends(get_db)):
    model = update_model(model_id, model_update, db=db)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@router.get("/{model_id}/factor-weights", response_model=List[ModelFactorWeightOut])
def read_model_factor_weights(model_id: int, db: Session = Depends(get_db)):
    weights = get_model_factor_weights(model_id, db=db)
    return weights

@router.post("/{model_id}/factor-weights", response_model=List[ModelFactorWeightOut])
def create_model_factor_weights_endpoint(model_id: int, weights: List[ModelFactorWeightCreate], db: Session = Depends(get_db)):
    return create_model_factor_weights(model_id, weights, db=db)

@router.put("/{model_id}/factor-weights", response_model=List[ModelFactorWeightOut])
def update_model_factor_weights_endpoint(model_id: int, weights: List[ModelFactorWeightCreate], db: Session = Depends(get_db)):
    return update_model_factor_weights(model_id, weights, db=db)

@router.get("/{model_id}/scores", response_model=List[ModelScoreOut])
def read_model_scores(model_id: int, trade_date: str, selected_only: bool = False, db: Session = Depends(get_db)):
    scores = get_model_scores(model_id, trade_date, selected_only, db=db)
    return scores

@router.post("/{model_id}/score", response_model=List[ModelScoreOut])
def calculate_model_scores_endpoint(model_id: int, trade_date: str, db: Session = Depends(get_db)):
    return calculate_model_scores(model_id, trade_date, db=db)

@router.get("/{model_id}/performance", response_model=List[ModelPerformanceOut])
def read_model_performance(model_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    perf = db.query(ModelPerformance).filter(
        ModelPerformance.model_id == model_id
    ).order_by(ModelPerformance.trade_date.desc()).offset(skip).limit(limit).all()
    return perf