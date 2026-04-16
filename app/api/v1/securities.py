from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.securities_service import get_securities, get_security_by_ts_code, create_security, update_security, delete_security
from app.models.securities import Security
from app.schemas.securities import SecurityCreate, SecurityUpdate, SecurityOut

router = APIRouter()

@router.get("/", response_model=List[SecurityOut])
def read_securities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    securities = get_securities(skip=skip, limit=limit, db=db)
    return securities

@router.get("/{ts_code}", response_model=SecurityOut)
def read_security(ts_code: str, db: Session = Depends(get_db)):
    security = get_security_by_ts_code(ts_code, db=db)
    if security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return security

@router.post("/", response_model=SecurityOut)
def create_security_endpoint(security: SecurityCreate, db: Session = Depends(get_db)):
    return create_security(security, db=db)

@router.put("/{security_id}", response_model=SecurityOut)
def update_security_endpoint(security_id: int, security_update: SecurityUpdate, db: Session = Depends(get_db)):
    security = update_security(security_id, security_update, db=db)
    if security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return security

@router.delete("/{security_id}")
def delete_security_endpoint(security_id: int, db: Session = Depends(get_db)):
    success = delete_security(security_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Security not found")
    return {"message": "Security deleted successfully"}
