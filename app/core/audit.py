"""
审计日志服务

提供防篡改的审计日志功能：
- 哈希链算法确保日志完整性
- 自动记录关键操作
- 验证日志链完整性
- 检测篡改行为
"""

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditService:
    """审计日志服务"""

    def __init__(self, db: Session):
        self.db = db

    def _calculate_hash(
        self,
        created_at: datetime,
        user_id: int | None,
        action: str,
        resource_type: str | None,
        resource_id: str | None,
        previous_hash: str | None,
        extra_data: str | None = None,
    ) -> str:
        """
        计算记录的哈希值

        Args:
            created_at: 创建时间
            user_id: 用户 ID
            action: 操作类型
            resource_type: 资源类型
            resource_id: 资源 ID
            previous_hash: 前一条记录的哈希值
            extra_data: 额外元数据

        Returns:
            SHA-256 哈希值（64 字符十六进制字符串）
        """
        # 构建哈希输入
        hash_input = {
            "created_at": created_at.isoformat() if created_at else None,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "previous_hash": previous_hash,
            "extra_data": extra_data,
        }

        # 转换为 JSON 字符串（确保顺序一致）
        hash_string = json.dumps(hash_input, sort_keys=True, ensure_ascii=False)

        # 计算 SHA-256 哈希
        return hashlib.sha256(hash_string.encode("utf-8")).hexdigest()

    def _get_last_log(self) -> AuditLog | None:
        """获取最后一条审计日志"""
        stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(1)
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def log(
        self,
        action: str,
        user_id: int | None = None,
        username: str | None = None,
        ip_address: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        description: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """
        记录审计日志

        Args:
            action: 操作类型（如 "user.login", "data.update"）
            user_id: 用户 ID
            username: 用户名
            ip_address: IP 地址
            resource_type: 资源类型（如 "strategy", "portfolio"）
            resource_id: 资源 ID
            description: 操作描述
            method: HTTP 方法
            path: 请求路径
            status_code: HTTP 状态码
            metadata: 额外元数据

        Returns:
            创建的审计日志记录
        """
        # 获取前一条记录的哈希值
        last_log = self._get_last_log()
        previous_hash = last_log.current_hash if last_log else None

        # 序列化元数据
        extra_data_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

        # 创建时间
        created_at = datetime.utcnow()

        # 计算当前记录的哈希值
        current_hash = self._calculate_hash(
            created_at=created_at,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_hash=previous_hash,
            extra_data=extra_data_json,
        )

        # 创建审计日志记录
        audit_log = AuditLog(
            created_at=created_at,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            method=method,
            path=path,
            status_code=status_code,
            extra_data=extra_data_json,
            previous_hash=previous_hash,
            current_hash=current_hash,
        )

        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)

        return audit_log

    def verify_chain(self, start_id: int | None = None, end_id: int | None = None) -> dict[str, Any]:
        """
        验证审计日志链的完整性

        Args:
            start_id: 起始记录 ID（None 表示从第一条开始）
            end_id: 结束记录 ID（None 表示到最后一条）

        Returns:
            验证结果字典：
            {
                "valid": bool,  # 链是否完整
                "total": int,  # 总记录数
                "verified": int,  # 已验证记录数
                "errors": list,  # 错误列表
            }
        """
        # 构建查询
        stmt = select(AuditLog).order_by(AuditLog.id)
        if start_id is not None:
            stmt = stmt.where(AuditLog.id >= start_id)
        if end_id is not None:
            stmt = stmt.where(AuditLog.id <= end_id)

        result = self.db.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return {"valid": True, "total": 0, "verified": 0, "errors": []}

        errors = []
        previous_hash = None

        for i, log in enumerate(logs):
            # 检查 previous_hash 是否匹配
            if log.previous_hash != previous_hash:
                errors.append(
                    {
                        "log_id": log.id,
                        "error": "previous_hash_mismatch",
                        "expected": previous_hash,
                        "actual": log.previous_hash,
                    }
                )

            # 重新计算哈希值
            calculated_hash = self._calculate_hash(
                created_at=log.created_at,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                previous_hash=log.previous_hash,
                extra_data=log.extra_data,
            )

            # 检查哈希值是否匹配
            if calculated_hash != log.current_hash:
                errors.append(
                    {
                        "log_id": log.id,
                        "error": "hash_mismatch",
                        "expected": calculated_hash,
                        "actual": log.current_hash,
                    }
                )

            previous_hash = log.current_hash

        return {
            "valid": len(errors) == 0,
            "total": len(logs),
            "verified": len(logs),
            "errors": errors,
        }

    def get_logs(
        self,
        user_id: int | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        查询审计日志

        Args:
            user_id: 用户 ID
            action: 操作类型
            resource_type: 资源类型
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回记录数限制
            offset: 偏移量

        Returns:
            审计日志列表
        """
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())

        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if start_time is not None:
            stmt = stmt.where(AuditLog.created_at >= start_time)
        if end_time is not None:
            stmt = stmt.where(AuditLog.created_at <= end_time)

        stmt = stmt.limit(limit).offset(offset)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def detect_tampering(self) -> dict[str, Any]:
        """
        检测审计日志是否被篡改

        Returns:
            检测结果字典：
            {
                "tampered": bool,  # 是否被篡改
                "issues": list,  # 问题列表
            }
        """
        verification = self.verify_chain()

        issues = []

        # 检查哈希链完整性
        if not verification["valid"]:
            issues.extend(verification["errors"])

        # 检查是否有记录被删除（ID 不连续）
        stmt = select(AuditLog.id).order_by(AuditLog.id)
        result = self.db.execute(stmt)
        ids = [row[0] for row in result.all()]

        if ids:
            expected_ids = list(range(ids[0], ids[-1] + 1))
            missing_ids = set(expected_ids) - set(ids)
            if missing_ids:
                issues.append(
                    {
                        "error": "missing_records",
                        "missing_ids": sorted(missing_ids),
                    }
                )

        return {
            "tampered": len(issues) > 0,
            "issues": issues,
        }
