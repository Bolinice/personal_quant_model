from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.stock_pool_service import get_stock_pools, get_stock_pool_by_code, create_stock_pool, update_stock_pool, get_stock_pool_snapshot, create_stock_pool_snapshot
from app.models.stock_pools import StockPool, StockPoolSnapshot
from app.schemas.stock_pools import StockPoolCreate, StockPoolUpdate, StockPoolOut, StockPoolSnapshotCreate, StockPoolSnapshotOut

router = APIRouter()

@router.get("/", response_model=List[StockPoolOut])
def read_stock_pools(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    pools = get_stock_pools(skip=skip, limit=limit, db=db)
    return pools

@router.get("/{pool_code}", response_model=StockPoolOut)
def read_stock_pool(pool_code: str, db: Session = Depends(get_db)):
    pool = get_stock_pool_by_code(pool_code, db=db)
    if pool is None:
        raise HTTPException(status_code=404, detail="Stock pool not found")
    return pool

@router.post("/", response_model=StockPoolOut)
def create_stock_pool_endpoint(pool: StockPoolCreate, db: Session = Depends(get_db)):
    return create_stock_pool(pool, db=db)

@router.put("/{pool_id}", response_model=StockPoolOut)
def update_stock_pool_endpoint(pool_id: int, pool_update: StockPoolUpdate, db: Session = Depends(get_db)):
    pool = update_stock_pool(pool_id, pool_update, db=db)
    if pool is None:
        raise HTTPException(status_code=404, detail="Stock pool not found")
    return pool

@router.get("/{pool_id}/snapshots", response_model=List[StockPoolSnapshotOut])
def read_stock_pool_snapshots(pool_id: int, trade_date: str = None, eligible_only: bool = False, db: Session = Depends(get_db)):
    if trade_date:
        snapshot = get_stock_pool_snapshot(pool_id, trade_date, db=db)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return [snapshot]
    
    # 这里应该实现查询多个快照的逻辑
    return []

@router.post("/{pool_id}/snapshots", response_model=StockPoolSnapshotOut)
def create_stock_pool_snapshot_endpoint(pool_id: int, snapshot: StockPoolSnapshotCreate, db: Session = Depends(get_db)):
    return create_stock_pool_snapshot(pool_id, snapshot.trade_date, snapshot.securities, snapshot.eligible_count, db=db)
