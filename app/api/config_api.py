"""
配置中心 REST API

提供配置管理的HTTP接口
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config_center import get_config_center

router = APIRouter(prefix="/api/config", tags=["配置管理"])


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""

    key: str
    value: Any
    author: str = "api"


class ConfigRollbackRequest(BaseModel):
    """配置回滚请求"""

    version: str


@router.get("/")
async def get_all_config():
    """获取所有配置"""
    config_center = get_config_center()
    return {"config": config_center.get_all()}


@router.get("/{key:path}")
async def get_config_value(key: str):
    """获取指定配置值"""
    config_center = get_config_center()
    value = config_center.get(key)

    if value is None:
        raise HTTPException(status_code=404, detail=f"配置不存在: {key}")

    return {"key": key, "value": value}


@router.post("/")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    config_center = get_config_center()

    try:
        config_center.set(request.key, request.value, author=request.author)
        return {"message": "配置已更新", "key": request.key, "value": request.value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/versions/list")
async def get_version_history(limit: int = 10):
    """获取版本历史"""
    config_center = get_config_center()
    versions = config_center.get_version_history(limit=limit)

    return {
        "versions": [
            {
                "version": v.version,
                "timestamp": v.timestamp,
                "author": v.author,
                "description": v.description,
            }
            for v in versions
        ]
    }


@router.post("/versions/rollback")
async def rollback_config(request: ConfigRollbackRequest):
    """回滚配置"""
    config_center = get_config_center()

    try:
        config_center.rollback(request.version)
        return {"message": f"配置已回滚到版本: {request.version}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reload")
async def reload_config():
    """重新加载配置"""
    config_center = get_config_center()

    try:
        config_center.reload()
        return {"message": "配置已重新加载"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate")
async def validate_config():
    """验证配置"""
    config_center = get_config_center()
    config = config_center.get_all()

    errors = []

    # 验证交易成本
    costs = config.get("backtest", {}).get("costs", {})
    if costs:
        for key in ["commission_rate", "stamp_tax_rate", "slippage_rate"]:
            value = costs.get(key)
            if value is not None and not (0 <= value <= 0.01):
                errors.append(f"backtest.costs.{key} 超出范围 [0, 0.01]: {value}")

    # 验证风险参数
    risk = config.get("risk", {})
    if risk:
        max_position = risk.get("max_position")
        if max_position is not None and not (0 < max_position <= 1):
            errors.append(f"risk.max_position 超出范围 (0, 1]: {max_position}")

    if errors:
        return {"valid": False, "errors": errors}
    else:
        return {"valid": True, "message": "配置验证通过"}
