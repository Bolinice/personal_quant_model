"""任务日志 API。"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.task_logs_service import get_task_logs, create_task_log, get_task_log_by_id, update_task_log, delete_task_log
from app.schemas.task_logs import TaskLogCreate, TaskLogUpdate, TaskLogOut
from app.core.response import success, error

router = APIRouter()


@router.get("/")
def read_task_logs(skip: int = 0, limit: int = 100, task_type: str = None, status: str = None, db: Session = Depends(get_db)):
    """获取任务日志列表"""
    logs = get_task_logs(skip=skip, limit=limit, task_type=task_type, status=status, db=db)
    return success(logs)


@router.get("/{log_id}")
def read_task_log(log_id: int, db: Session = Depends(get_db)):
    """获取任务日志详情"""
    log = get_task_log_by_id(log_id, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Task log not found")
    return success(log)


@router.post("/")
def create_task_log_endpoint(log: TaskLogCreate, db: Session = Depends(get_db)):
    """创建任务日志"""
    result = create_task_log(log, db=db)
    return success(result)


@router.put("/{log_id}")
def update_task_log_endpoint(log_id: int, log_update: TaskLogUpdate, db: Session = Depends(get_db)):
    """更新任务日志"""
    log = update_task_log(log_id, log_update, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Task log not found")
    return success(log)


@router.delete("/{log_id}")
def delete_task_log_endpoint(log_id: int, db: Session = Depends(get_db)):
    """删除任务日志"""
    deleted = delete_task_log(log_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task log not found")
    return success(message="Task log deleted successfully")