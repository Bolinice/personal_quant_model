from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.services.task_logs_service import get_task_logs, create_task_log, get_task_log_by_id, update_task_log, delete_task_log
from app.models.task_logs import TaskLog
from app.schemas.task_logs import TaskLogCreate, TaskLogUpdate, TaskLogOut

router = APIRouter()

@router.get("/", response_model=list[TaskLogOut])
def read_task_logs(skip: int = 0, limit: int = 100, task_type: str = None, status: str = None, db: Session = Depends(SessionLocal)):
    logs = get_task_logs(skip=skip, limit=limit, task_type=task_type, status=status, db=db)
    return logs

@router.get("/{log_id}", response_model=TaskLogOut)
def read_task_log(log_id: int, db: Session = Depends(SessionLocal)):
    log = get_task_log_by_id(log_id, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Task log not found")
    return log

@router.post("/", response_model=TaskLogOut)
def create_task_log_endpoint(log: TaskLogCreate, db: Session = Depends(SessionLocal)):
    return create_task_log(log, db=db)

@router.put("/{log_id}", response_model=TaskLogOut)
def update_task_log_endpoint(log_id: int, log_update: TaskLogUpdate, db: Session = Depends(SessionLocal)):
    log = update_task_log(log_id, log_update, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Task log not found")
    return log

@router.delete("/{log_id}")
def delete_task_log_endpoint(log_id: int, db: Session = Depends(SessionLocal)):
    success = delete_task_log(log_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Task log not found")
    return {"message": "Task log deleted successfully"}