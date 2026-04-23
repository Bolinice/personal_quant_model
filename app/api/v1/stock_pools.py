"""股票池管理 API。"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.stock_pool_service import get_stock_pools, get_stock_pool_by_code, create_stock_pool, update_stock_pool, get_stock_pool_snapshot, create_stock_pool_snapshot
from app.schemas.stock_pools import StockPoolCreate, StockPoolUpdate, StockPoolOut, StockPoolSnapshotCreate, StockPoolSnapshotOut
from app.core.response import success, error

router = APIRouter()


@router.get("/")
def read_stock_pools(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取股票池列表"""
    pools = get_stock_pools(skip=skip, limit=limit, db=db)
    return success(pools)


@router.get("/{pool_code}")
def read_stock_pool(pool_code: str, db: Session = Depends(get_db)):
    """获取股票池详情"""
    pool = get_stock_pool_by_code(pool_code, db=db)
    if pool is None:
        raise HTTPException(status_code=404, detail="Stock pool not found")
    return success(pool)


@router.post("/")
def create_stock_pool_endpoint(pool: StockPoolCreate, db: Session = Depends(get_db)):
    """创建股票池"""
    result = create_stock_pool(pool, db=db)
    return success(result)


@router.put("/{pool_id}")
def update_stock_pool_endpoint(pool_id: int, pool_update: StockPoolUpdate, db: Session = Depends(get_db)):
    """更新股票池"""
    pool = update_stock_pool(pool_id, pool_update, db=db)
    if pool is None:
        raise HTTPException(status_code=404, detail="Stock pool not found")
    return success(pool)


@router.get("/{pool_id}/snapshots")
def read_stock_pool_snapshots(pool_id: int, trade_date: str = None, eligible_only: bool = False, db: Session = Depends(get_db)):
    """获取股票池快照"""
    if trade_date:
        snapshot = get_stock_pool_snapshot(pool_id, trade_date, db=db)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return success([snapshot])
    return success([])


@router.post("/{pool_id}/snapshots")
def create_stock_pool_snapshot_endpoint(pool_id: int, snapshot: StockPoolSnapshotCreate, db: Session = Depends(get_db)):
    """创建股票池快照"""
    result = create_stock_pool_snapshot(pool_id, snapshot.trade_date, snapshot.securities, snapshot.eligible_count, db=db)
    return success(result)