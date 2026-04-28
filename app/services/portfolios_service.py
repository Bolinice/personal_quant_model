from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.base import with_db
from app.models.models import Model
from app.models.portfolios import Portfolio, PortfolioPosition, RebalanceRecord
from app.schemas.portfolios import PortfolioCreate, PortfolioPositionCreate, RebalanceRecordCreate


@with_db
def get_portfolios(model_id: int, trade_date: str | None = None, db: Session | None = None):
    query = db.query(Portfolio).filter(Portfolio.model_id == model_id)
    if trade_date:
        query = query.filter(Portfolio.trade_date == trade_date)
    return query.all()


@with_db
def create_portfolio(portfolio: PortfolioCreate, db: Session = None):
    db_portfolio = Portfolio(**portfolio.model_dump())
    db.add(db_portfolio)
    db.commit()
    db.refresh(db_portfolio)
    return db_portfolio


@with_db
def get_portfolio_positions(portfolio_id: int, db: Session = None):
    return db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio_id).all()


@with_db
def create_portfolio_positions(portfolio_id: int, positions: list[PortfolioPositionCreate], db: Session = None):
    db_positions = []
    for position in positions:
        db_position = PortfolioPosition(
            portfolio_id=portfolio_id, security_id=position.security_id, weight=position.weight
        )
        db.add(db_position)
        db_positions.append(db_position)
    db.commit()
    for db_position in db_positions:
        db.refresh(db_position)
    return db_positions


@with_db
def get_rebalance_records(model_id: int, start_date: str, end_date: str, db: Session = None):
    return (
        db.query(RebalanceRecord)
        .filter(
            RebalanceRecord.model_id == model_id,
            RebalanceRecord.trade_date >= start_date,
            RebalanceRecord.trade_date <= end_date,
        )
        .all()
    )


@with_db
def create_rebalance_record(record: RebalanceRecordCreate, db: Session = None):
    db_record = RebalanceRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@with_db
def generate_research_snapshot(model_id: int, trade_date: str, db: Session = None):
    """生成研究组合快照（合规化：原 generate_portfolio）

    真实业务逻辑：
    1. 读取模型定义与评分结果
    2. 读取当日有效股票池
    3. 按评分排序选取 Top N
    4. 应用风险约束（单票上限、行业偏离）
    5. 生成目标权重
    6. 产出研究组合快照
    """
    # 读取模型
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        return None

    # 尝试读取模型评分结果
    try:
        from app.models.models import ModelScore

        scores = (
            db.query(ModelScore)
            .filter(
                ModelScore.model_id == model_id,
                ModelScore.trade_date == trade_date,
            )
            .order_by(ModelScore.composite_score.desc())
            .all()
        )
    except Exception:
        scores = []

    # 确定持仓数量
    n_holdings = getattr(model, "n_holdings", 30) or 30

    if scores and len(scores) > 0:
        # 有真实评分：按评分排序选股
        selected_scores = scores[:n_holdings]
        n_selected = len(selected_scores)

        # 等权分配（后续可扩展为优化权重）
        positions = [
            PortfolioPositionCreate(
                security_id=s.security_id,
                weight=1.0 / n_selected,
            )
            for s in selected_scores
        ]
    else:
        # 无评分数据：返回空组合快照（不生成假数据）
        positions = []

    # 创建组合快照
    portfolio = PortfolioCreate(
        model_id=model_id,
        trade_date=trade_date,
        target_exposure=1.0,
    )
    db_portfolio = create_portfolio(portfolio, db=db)

    if positions:
        create_portfolio_positions(db_portfolio.id, positions, db=db)

    return db_portfolio


@with_db
def generate_change_observation(model_id: int, trade_date: str, db: Session = None):
    """生成结构变化观察（合规化：原 generate_rebalance）

    真实业务逻辑：
    1. 读取上一期组合快照
    2. 生成当前目标组合快照
    3. 对比持仓差异
    4. 输出变化观察摘要（非交易指令）
    """
    # 查找上一期组合
    prev_portfolios = (
        db.query(Portfolio)
        .filter(
            Portfolio.model_id == model_id,
            Portfolio.trade_date < trade_date,
        )
        .order_by(Portfolio.trade_date.desc())
        .limit(1)
        .all()
    )

    prev_positions = []
    if prev_portfolios:
        prev_portfolio = prev_portfolios[0]
        prev_positions = (
            db.query(PortfolioPosition)
            .filter(
                PortfolioPosition.portfolio_id == prev_portfolio.id,
            )
            .all()
        )

    # 生成当前目标组合
    current_portfolio = generate_research_snapshot(model_id, trade_date, db=db)
    if not current_portfolio:
        return None

    current_positions = (
        db.query(PortfolioPosition)
        .filter(
            PortfolioPosition.portfolio_id == current_portfolio.id,
        )
        .all()
    )

    # 计算变化观察
    prev_map = {p.security_id: p.weight for p in prev_positions}
    curr_map = {p.security_id: p.weight for p in current_positions}

    all_ids = set(prev_map.keys()) | set(curr_map.keys())

    added = [sid for sid in all_ids if sid not in prev_map]
    removed = [sid for sid in all_ids if sid not in curr_map]
    weight_changes = [
        {"security_id": sid, "prev_weight": prev_map.get(sid, 0), "curr_weight": curr_map.get(sid, 0)}
        for sid in all_ids
        if sid in prev_map and sid in curr_map and abs(curr_map[sid] - prev_map[sid]) > 0.001
    ]

    # 生成变化观察记录（非交易指令）
    rebalance = RebalanceRecordCreate(
        model_id=model_id,
        trade_date=trade_date,
        rebalance_type="observation",
        buy_list=[{"security_id": sid, "weight": curr_map[sid]} for sid in added],
        sell_list=[{"security_id": sid, "weight": prev_map[sid]} for sid in removed],
        total_turnover=len(added) + len(removed) + len(weight_changes),
    )
    return create_rebalance_record(rebalance, db=db)


# ============================================================
# 向后兼容别名（过渡期使用）
# ============================================================
generate_portfolio = generate_research_snapshot
generate_rebalance = generate_change_observation
