from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.securities import Security
from app.schemas.securities import SecurityCreate, SecurityUpdate

def get_securities(skip: int = 0, limit: int = 100, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(Security).offset(skip).limit(limit).all()
        finally:
            db.close()
    return db.query(Security).offset(skip).limit(limit).all()

def get_security_by_ts_code(ts_code: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(Security).filter(Security.ts_code == ts_code).first()
        finally:
            db.close()
    return db.query(Security).filter(Security.ts_code == ts_code).first()

def create_security(security: SecurityCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_security = Security(**security.dict())
            db.add(db_security)
            db.commit()
            db.refresh(db_security)
            return db_security
        finally:
            db.close()
    db_security = Security(**security.dict())
    db.add(db_security)
    db.commit()
    db.refresh(db_security)
    return db_security

def update_security(security_id: int, security_update: SecurityUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_security = db.query(Security).filter(Security.id == security_id).first()
            if not db_security:
                return None
            update_data = security_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_security, key, value)
            db.commit()
            db.refresh(db_security)
            return db_security
        finally:
            db.close()
    db_security = db.query(Security).filter(Security.id == security_id).first()
    if not db_security:
        return None
    update_data = security_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_security, key, value)
    db.commit()
    db.refresh(db_security)
    return db_security

def delete_security(security_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_security = db.query(Security).filter(Security.id == security_id).first()
            if db_security:
                db.delete(db_security)
                db.commit()
                return True
            return False
        finally:
            db.close()
    db_security = db.query(Security).filter(Security.id == security_id).first()
    if db_security:
        db.delete(db_security)
        db.commit()
        return True
    return False
