from sqlalchemy.orm import Session

from app.db.base import with_db
from app.models.securities import Security
from app.schemas.securities import SecurityCreate, SecurityUpdate


@with_db
def get_securities(skip: int = 0, limit: int = 100, db: Session = None):
    return db.query(Security).offset(skip).limit(limit).all()


@with_db
def get_security_by_ts_code(ts_code: str, db: Session = None):
    return db.query(Security).filter(Security.ts_code == ts_code).first()


@with_db
def create_security(security: SecurityCreate, db: Session = None):
    db_security = Security(**security.model_dump())
    db.add(db_security)
    db.commit()
    db.refresh(db_security)
    return db_security


@with_db
def update_security(security_id: int, security_update: SecurityUpdate, db: Session = None):
    db_security = db.query(Security).filter(Security.id == security_id).first()
    if not db_security:
        return None
    update_data = security_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_security, key, value)
    db.commit()
    db.refresh(db_security)
    return db_security


@with_db
def delete_security(security_id: int, db: Session = None):
    db_security = db.query(Security).filter(Security.id == security_id).first()
    if db_security:
        db.delete(db_security)
        db.commit()
        return True
    return False
