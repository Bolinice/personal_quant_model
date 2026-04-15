from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.task_logs import TaskLog
from app.schemas.task_logs import TaskLogCreate, TaskLogUpdate, TaskLogOut

def get_task_logs(skip: int = 0, limit: int = 100, task_type: str = None, status: str = None, db: Session = None):
    if db is None:
        db = SessionLocal()
    query = db.query(TaskLog)
    if task_type:
        query = query.filter(TaskLog.task_type == task_type)
    if status:
        query = query.filter(TaskLog.status == status)
    return query.offset(skip).limit(limit).all()

def get_task_log_by_id(log_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    return db.query(TaskLog).filter(TaskLog.id == log_id).first()

def create_task_log(log: TaskLogCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_log = TaskLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def update_task_log(log_id: int, log_update: TaskLogUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_log = get_task_log_by_id(log_id, db)
    if db_log is None:
        return None
    for var, value in log_update.dict(exclude_unset=True).items():
        setattr(db_log, var, value)
    db.commit()
    db.refresh(db_log)
    return db_log

def delete_task_log(log_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_log = get_task_log_by_id(log_id, db)
    if db_log is None:
        return False
    db.delete(db_log)
    db.commit()
    return True