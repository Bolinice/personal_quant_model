"""
权限模型
- Permission: 权限定义
- RolePermission: 角色-权限关联
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Permission(Base):
    """权限定义表"""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True, comment="权限编码")
    name = Column(String(128), nullable=False, comment="权限名称")
    description = Column(Text, nullable=True, comment="权限描述")
    category = Column(String(64), nullable=True, comment="权限分类: factor/backtest/portfolio/report/api")
    created_at = Column(DateTime, default=datetime.utcnow)

    role_permissions = relationship("RolePermission", back_populates="permission")

    def __repr__(self):
        return f"<Permission(code={self.code}, name={self.name})>"


class RolePermission(Base):
    """角色-权限关联表"""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role", "permission_id", name="uq_role_permission"),)

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(32), nullable=False, index=True, comment="角色: trial/free/pro/institution")
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    permission = relationship("Permission", back_populates="role_permissions")

    def __repr__(self):
        return f"<RolePermission(role={self.role}, permission_id={self.permission_id})>"


# ============================================================
# 预定义权限码
# ============================================================
PERMISSION_CODES = {
    # 因子分析
    "factor_view_basic": "查看基础因子（10个核心因子）",
    "factor_view_all": "查看全部因子库",
    "factor_ic_analysis": "因子IC分析",
    "factor_decay_monitor": "因子衰减监控",
    # 回测
    "backtest_daily_1": "每日1次策略回测",
    "backtest_unlimited": "无限策略回测",
    "backtest_batch": "批量回测",
    # 组合
    "portfolio_view": "查看组合列表",
    "portfolio_track": "组合跟踪（创建研究快照）",
    "portfolio_change_observe": "结构变化观察",
    # 报告
    "report_view": "查看报告",
    "report_export": "导出报告",
    # 数据
    "data_view": "查看市场数据",
    "data_export": "数据导出",
    # API
    "api_access": "API接口访问",
    # 信号
    "signal_push": "量化信号推送",
}

# 角色-权限映射
ROLE_PERMISSIONS = {
    "trial": [
        "factor_view_basic",
        "backtest_daily_1",
        "portfolio_view",
        "data_view",
        "report_view",
    ],
    "free": [
        "factor_view_basic",
        "backtest_daily_1",
        "portfolio_view",
        "data_view",
        "report_view",
    ],
    "pro": [
        "factor_view_all",
        "factor_ic_analysis",
        "factor_decay_monitor",
        "backtest_unlimited",
        "portfolio_view",
        "portfolio_track",
        "portfolio_change_observe",
        "report_view",
        "report_export",
        "data_view",
        "data_export",
        "signal_push",
    ],
    "institution": [
        "factor_view_all",
        "factor_ic_analysis",
        "factor_decay_monitor",
        "backtest_unlimited",
        "backtest_batch",
        "portfolio_view",
        "portfolio_track",
        "portfolio_change_observe",
        "report_view",
        "report_export",
        "data_view",
        "data_export",
        "signal_push",
        "api_access",
    ],
}
