"""
审计日志 API

提供审计日志查询、验证、检测篡改等功能
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.audit import AuditService
from app.db.base import get_db

router = APIRouter(prefix="/audit", tags=["审计日志"])


@router.get("/logs")
async def get_audit_logs(
    user_id: int | None = Query(None, description="用户 ID"),
    action: str | None = Query(None, description="操作类型"),
    resource_type: str | None = Query(None, description="资源类型"),
    start_time: datetime | None = Query(None, description="开始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    查询审计日志

    支持按用户、操作类型、资源类型、时间范围过滤
    """
    audit_service = AuditService(db)

    logs = audit_service.get_logs(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    # 转换为字典
    logs_data = [
        {
            "id": log.id,
            "created_at": log.created_at.isoformat(),
            "user_id": log.user_id,
            "username": log.username,
            "ip_address": log.ip_address,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "extra_data": log.extra_data,
            "previous_hash": log.previous_hash,
            "current_hash": log.current_hash,
        }
        for log in logs
    ]

    return {
        "code": 0,
        "message": "success",
        "data": {
            "logs": logs_data,
            "total": len(logs_data),
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/verify")
async def verify_audit_chain(
    start_id: int | None = Query(None, description="起始记录 ID"),
    end_id: int | None = Query(None, description="结束记录 ID"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    验证审计日志链的完整性

    检查哈希链是否完整，是否有记录被篡改
    """
    audit_service = AuditService(db)

    verification = audit_service.verify_chain(start_id=start_id, end_id=end_id)

    return {
        "code": 0,
        "message": "success",
        "data": verification,
    }


@router.get("/detect-tampering")
async def detect_tampering(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    检测审计日志是否被篡改

    检查哈希链完整性和记录是否被删除
    """
    audit_service = AuditService(db)

    detection = audit_service.detect_tampering()

    if detection["tampered"]:
        return {
            "code": 1,
            "message": "审计日志已被篡改",
            "data": detection,
        }

    return {
        "code": 0,
        "message": "审计日志完整",
        "data": detection,
    }


@router.post("/log")
async def create_audit_log(
    action: str = Query(..., description="操作类型"),
    user_id: int | None = Query(None, description="用户 ID"),
    username: str | None = Query(None, description="用户名"),
    ip_address: str | None = Query(None, description="IP 地址"),
    resource_type: str | None = Query(None, description="资源类型"),
    resource_id: str | None = Query(None, description="资源 ID"),
    description: str | None = Query(None, description="操作描述"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    手动创建审计日志

    用于测试或特殊场景
    """
    audit_service = AuditService(db)

    log = audit_service.log(
        action=action,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
    )

    return {
        "code": 0,
        "message": "success",
        "data": {
            "id": log.id,
            "created_at": log.created_at.isoformat(),
            "action": log.action,
            "current_hash": log.current_hash,
        },
    }
