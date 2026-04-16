from sqlalchemy.orm import Session

from typing import List
from app.db.base import with_db
from app.models.stock_pools import StockPool, StockPoolSnapshot
from app.schemas.stock_pools import StockPoolCreate, StockPoolUpdate, FilterConfig

@with_db
def get_stock_pools(skip: int = 0, limit: int = 100, db: Session = None):
    return db.query(StockPool).offset(skip).limit(limit).all()

@with_db
def get_stock_pool_by_code(pool_code: str, db: Session = None):
    return db.query(StockPool).filter(StockPool.pool_code == pool_code).first()

@with_db
def create_stock_pool(pool: StockPoolCreate, db: Session = None):
    db_pool = StockPool(**pool.dict())
    db.add(db_pool)
    db.commit()
    db.refresh(db_pool)
    return db_pool

@with_db
def update_stock_pool(pool_id: int, pool_update: StockPoolUpdate, db: Session = None):
    db_pool = db.query(StockPool).filter(StockPool.id == pool_id).first()
    if not db_pool:
        return None
    update_data = pool_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_pool, key, value)
    db.commit()
    db.refresh(db_pool)
    return db_pool

@with_db
def get_stock_pool_snapshot(pool_id: int, trade_date: str, db: Session = None):
    return db.query(StockPoolSnapshot).filter(
        StockPoolSnapshot.pool_id == pool_id,
        StockPoolSnapshot.trade_date == trade_date
    ).first()

@with_db
def create_stock_pool_snapshot(pool_id: int, trade_date: str, securities: List[str], eligible_count: int, db: Session = None):
    db_snapshot = StockPoolSnapshot(
        pool_id=pool_id,
        trade_date=trade_date,
        securities=securities,
        eligible_count=eligible_count
    )
    db.add(db_snapshot)
    db.commit()
    db.refresh(db_snapshot)
    return db_snapshot

def apply_filters(securities: list, filter_config: FilterConfig):
    filtered_securities = []
    for security in securities:
        # 这里应该根据filter_config应用过滤规则
        # 示例：过滤ST股票
        if filter_config.exclude_st and security.get('is_st', False):
            continue
        # 示例：过滤停牌股票
        if filter_config.exclude_suspended and security.get('is_suspended', False):
            continue
        # 示例：过滤新股
        if filter_config.exclude_new_stock_days > 0:
            list_date = security.get('list_date')
            if list_date:
                days_since_list = (datetime.now() - list_date).days
                if days_since_list < filter_config.exclude_new_stock_days:
                    continue
        filtered_securities.append(security)
    return filtered_securities
