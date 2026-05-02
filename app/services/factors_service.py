from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from app.db.base import with_db
from app.models.factors import Factor, FactorAnalysis, FactorValue
from app.models.market import StockDaily, TradingCalendar
from app.schemas.factors import FactorAnalysisCreate, FactorCreate, FactorUpdate, FactorValueCreate

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session


@with_db
def get_next_trading_date(current_date: datetime, db: Session = None) -> datetime | None:
    """获取下一个交易日"""
    calendar = (
        db.query(TradingCalendar)
        .filter(TradingCalendar.cal_date > current_date.date(), TradingCalendar.is_open)
        .order_by(TradingCalendar.cal_date)
        .first()
    )
    return calendar.cal_date if calendar else None


@with_db
def get_trading_date_after(current_date: datetime, days: int, db: Session = None) -> datetime | None:
    """获取指定天数后的交易日"""
    calendars = (
        db.query(TradingCalendar)
        .filter(TradingCalendar.cal_date > current_date.date(), TradingCalendar.is_open)
        .order_by(TradingCalendar.cal_date)
        .limit(days + 1)
        .all()
    )
    return calendars[days].cal_date if len(calendars) > days else None


@with_db
def get_factors(
    skip: int = 0, limit: int = 100, category: str | None = None, status: str | None = None, db: Session | None = None
):
    query = db.query(Factor)
    if category:
        query = query.filter(Factor.category == category)
    if status:
        query = query.filter(Factor.is_active == (status == "active"))
    return query.offset(skip).limit(limit).all()


@with_db
def get_factor_by_code(factor_code: str, db: Session = None):
    return db.query(Factor).filter(Factor.factor_code == factor_code).first()


@with_db
def create_factor(factor: FactorCreate, db: Session = None):
    db_factor = Factor(**factor.model_dump())
    db.add(db_factor)
    db.commit()
    db.refresh(db_factor)
    return db_factor


@with_db
def update_factor(factor_id: int, factor_update: FactorUpdate, db: Session = None):
    db_factor = db.query(Factor).filter(Factor.id == factor_id).first()
    if not db_factor:
        return None
    update_data = factor_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_factor, key, value)
    db.commit()
    db.refresh(db_factor)
    return db_factor


@with_db
def get_factor_values(factor_id: int, trade_date: str, security_id: int | None = None, db: Session | None = None):
    query = db.query(FactorValue).filter(FactorValue.factor_id == factor_id, FactorValue.trade_date == trade_date)
    if security_id:
        query = query.filter(FactorValue.security_id == security_id)
    return query.all()


@with_db
def create_factor_values(factor_id: int, trade_date: str, values: list[FactorValueCreate], db: Session = None):
    db_values = []
    for value in values:
        db_value = FactorValue(
            factor_id=factor_id,
            trade_date=trade_date,
            security_id=value.security_id,
            value=value.value,
            is_valid=value.is_valid,
        )
        db.add(db_value)
        db_values.append(db_value)
    db.commit()
    for db_value in db_values:
        db.refresh(db_value)
    return db_values


@with_db
def get_factor_analysis(factor_id: int, start_date: str, end_date: str, db: Session = None):
    return (
        db.query(FactorAnalysis)
        .filter(
            FactorAnalysis.factor_id == factor_id,
            FactorAnalysis.analysis_date >= start_date,
            FactorAnalysis.analysis_date <= end_date,
        )
        .all()
    )


@with_db
def calculate_ic_analysis(factor_id: int, start_date: str, end_date: str, db: Session = None):
    """计算因子IC分析"""
    # 获取因子值和后续收益率
    factor_values = (
        db.query(FactorValue)
        .filter(
            FactorValue.factor_id == factor_id, FactorValue.trade_date >= start_date, FactorValue.trade_date <= end_date
        )
        .all()
    )

    if not factor_values:
        return None

    # 转换为DataFrame
    df = pd.DataFrame(
        [(v.security_id, v.trade_date, v.value) for v in factor_values],
        columns=["security_id", "trade_date", "factor_value"],
    )

    # 批量获取所有需要的交易日期
    unique_dates = df["trade_date"].unique()
    date_mapping = {}
    for date in unique_dates:
        next_date = get_next_trading_date(date)
        if next_date:
            date_mapping[date] = next_date

    # 批量获取所有股票的收益率数据（一次查询）
    all_security_ids = df["security_id"].unique().tolist()
    all_dates = list(date_mapping.values())

    stock_returns = (
        db.query(StockDaily.ts_code, StockDaily.trade_date, StockDaily.pct_chg)
        .filter(
            StockDaily.ts_code.in_(all_security_ids),
            StockDaily.trade_date.in_(all_dates)
        )
        .all()
    )

    # 构建收益率字典 {(ts_code, trade_date): pct_chg}
    returns_dict = {(r.ts_code, r.trade_date): r.pct_chg for r in stock_returns}

    # 映射下一日收益率
    df["next_return"] = df.apply(
        lambda row: returns_dict.get((row["security_id"], date_mapping.get(row["trade_date"])), 0),
        axis=1
    )

    # 计算IC
    ic = df["factor_value"].corr(df["next_return"])

    # 计算Rank IC
    rank_ic = df["factor_value"].rank().corr(df["next_return"].rank())

    # 计算IC衰减（批量查询优化）
    ic_decay = []
    for i in range(1, 21):  # 1-20日衰减
        # 批量获取滞后日期
        lag_date_mapping = {}
        for date in unique_dates:
            lag_date = get_trading_date_after(date, i)
            if lag_date:
                lag_date_mapping[date] = lag_date

        # 批量查询滞后期收益率
        lag_dates = list(lag_date_mapping.values())
        if not lag_dates:
            ic_decay.append(0)
            continue

        lag_returns = (
            db.query(StockDaily.ts_code, StockDaily.trade_date, StockDaily.pct_chg)
            .filter(
                StockDaily.ts_code.in_(all_security_ids),
                StockDaily.trade_date.in_(lag_dates)
            )
            .all()
        )

        lag_returns_dict = {(r.ts_code, r.trade_date): r.pct_chg for r in lag_returns}

        # 映射滞后收益率
        df[f"lag_{i}_return"] = df.apply(
            lambda row: lag_returns_dict.get((row["security_id"], lag_date_mapping.get(row["trade_date"])), 0),
            axis=1
        )

        # 计算滞后IC
        lag_ic = df["factor_value"].corr(df[f"lag_{i}_return"])
        ic_decay.append(lag_ic)

    # 保存分析结果
    analysis_data = FactorAnalysisCreate(
        analysis_type="ic_analysis", ic=ic, rank_ic=rank_ic, ic_decay=ic_decay, analysis_date=end_date
    )

    return create_factor_analysis(factor_id, analysis_data, db=db)


@with_db
def calculate_group_returns(factor_id: int, start_date: str, end_date: str, db: Session = None):
    """计算因子分层回测（分组收益）"""
    # 获取因子值
    factor_values = (
        db.query(FactorValue)
        .filter(
            FactorValue.factor_id == factor_id, FactorValue.trade_date >= start_date, FactorValue.trade_date <= end_date
        )
        .all()
    )

    if not factor_values:
        return None

    # 转换为DataFrame
    df = pd.DataFrame(
        [(v.security_id, v.trade_date, v.value) for v in factor_values],
        columns=["security_id", "trade_date", "factor_value"],
    )

    # 按因子值分组（10组）
    df["group"] = pd.qcut(df["factor_value"], 10, labels=False)

    # 批量获取所有需要的交易日期和收益率数据
    unique_dates = df["trade_date"].unique()
    date_mapping = {}
    for date in unique_dates:
        next_date = get_next_trading_date(date)
        if next_date:
            date_mapping[date] = next_date

    # 批量查询所有股票的收益率（一次查询）
    all_security_ids = df["security_id"].unique().tolist()
    all_dates = list(date_mapping.values())

    stock_returns = (
        db.query(StockDaily.ts_code, StockDaily.trade_date, StockDaily.pct_chg)
        .filter(
            StockDaily.ts_code.in_(all_security_ids),
            StockDaily.trade_date.in_(all_dates)
        )
        .all()
    )

    # 构建收益率字典
    returns_dict = {(r.ts_code, r.trade_date): r.pct_chg for r in stock_returns}

    # 映射下一日收益率
    df["next_return"] = df.apply(
        lambda row: returns_dict.get((row["security_id"], date_mapping.get(row["trade_date"])), 0),
        axis=1
    )

    # 计算每组平均收益率
    group_returns = []
    for group in range(10):
        group_df = df[df["group"] == group]
        if not group_df.empty:
            avg_return = group_df["next_return"].mean()
            group_returns.append(avg_return)
        else:
            group_returns.append(0)

    # 计算多空收益
    long_short_return = group_returns[9] - group_returns[0]  # 最高组 - 最低组

    # 保存分析结果
    analysis_data = FactorAnalysisCreate(
        analysis_type="group_returns",
        group_returns=group_returns,
        long_short_return=long_short_return,
        analysis_date=end_date,
    )

    return create_factor_analysis(factor_id, analysis_data, db=db)


@with_db
def calculate_factor_correlation(
    factor_id: int, compare_factor_id: int, start_date: str, end_date: str, db: Session = None
):
    """计算因子相关性分析"""
    # 获取两个因子的值
    factor1_values = (
        db.query(FactorValue)
        .filter(
            FactorValue.factor_id == factor_id, FactorValue.trade_date >= start_date, FactorValue.trade_date <= end_date
        )
        .all()
    )

    factor2_values = (
        db.query(FactorValue)
        .filter(
            FactorValue.factor_id == compare_factor_id,
            FactorValue.trade_date >= start_date,
            FactorValue.trade_date <= end_date,
        )
        .all()
    )

    if not factor1_values or not factor2_values:
        return None

    # 转换为DataFrame
    df1 = pd.DataFrame(
        [(v.security_id, v.trade_date, v.value) for v in factor1_values],
        columns=["security_id", "trade_date", "factor1_value"],
    )

    df2 = pd.DataFrame(
        [(v.security_id, v.trade_date, v.value) for v in factor2_values],
        columns=["security_id", "trade_date", "factor2_value"],
    )

    # 合并数据
    df = pd.merge(df1, df2, on=["security_id", "trade_date"])

    # 计算相关性
    correlation = df["factor1_value"].corr(df["factor2_value"])

    # 保存分析结果
    analysis_data = FactorAnalysisCreate(
        analysis_type="correlation",
        correlation=correlation,
        compare_factor_id=compare_factor_id,
        analysis_date=end_date,
    )

    return create_factor_analysis(factor_id, analysis_data, db=db)


@with_db
def create_factor_analysis(factor_id: int, analysis_data: FactorAnalysisCreate, db: Session = None):
    db_analysis = FactorAnalysis(**analysis_data.model_dump())
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    return db_analysis


@with_db
def calculate_factor_values(factor_id: int, trade_date: str, securities: list, db: Session = None):
    """因子计算入口 — 委托给FactorEngine执行实际计算"""
    from app.core.factor_engine import FactorEngine

    engine = FactorEngine(db)
    result_df = engine.calc_single_factor(factor_id, trade_date)
    if result_df is None or result_df.empty:
        return []

    values = []
    for _, row in result_df.iterrows():
        values.append(
            FactorValueCreate(
                security_id=row.get("security_id", row.get("ts_code", "")),
                value=float(row.get("value", 0)),
            )
        )
    return create_factor_values(factor_id, trade_date, values, db=db)


@with_db
def preprocess_factor_values(factor_id: int, trade_date: str, db: Session = None):
    """因子预处理：去极值、标准化、中性化"""
    # 获取因子值
    factor_values = get_factor_values(factor_id, trade_date, db=db)
    if not factor_values:
        return []

    # 转换为DataFrame
    df = pd.DataFrame([(v.security_id, v.value) for v in factor_values], columns=["security_id", "value"])

    # 去极值（MAD方法）
    median = df["value"].median()
    mad = np.median(np.abs(df["value"] - median))
    threshold = 3 * mad
    df["value"] = np.where(
        np.abs(df["value"] - median) > threshold, median + np.sign(df["value"] - median) * threshold, df["value"]
    )

    # 标准化（Z-score）
    mean = df["value"].mean()
    std = df["value"].std()
    df["value"] = (df["value"] - mean) / std

    # 更新数据库
    updated_values = []
    for _, row in df.iterrows():
        for fv in factor_values:
            if fv.security_id == row["security_id"]:
                fv.value = row["value"]
                updated_values.append(fv)
                break

    # 批量更新
    for fv in updated_values:
        db.add(fv)
    db.commit()

    return updated_values
