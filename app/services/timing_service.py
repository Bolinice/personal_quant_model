from typing import List
from sqlalchemy.orm import Session
from app.db.base import with_db
from app.models.timing import TimingSignal, TimingConfig
from app.schemas.timing import TimingSignalCreate, TimingConfigCreate
import pandas as pd
import numpy as np

@with_db
def get_timing_signals(model_id: int, start_date: str, end_date: str, db: Session = None):
    return db.query(TimingSignal).filter(
        TimingSignal.model_id == model_id,
        TimingSignal.trade_date >= start_date,
        TimingSignal.trade_date <= end_date
    ).all()

@with_db
def create_timing_signal(signal: TimingSignalCreate, db: Session = None):
    db_signal = TimingSignal(**signal.dict())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal

@with_db
def get_timing_config(model_id: int, db: Session = None):
    return db.query(TimingConfig).filter(TimingConfig.model_id == model_id).first()

@with_db
def create_timing_config(config: TimingConfigCreate, db: Session = None):
    db_config = TimingConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

@with_db
def update_timing_config(model_id: int, config_update: TimingConfigUpdate, db: Session = None):
    db_config = db.query(TimingConfig).filter(TimingConfig.model_id == model_id).first()
    if not db_config:
        return None
    update_data = config_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
    db.commit()
    db.refresh(db_config)
    return db_config

@with_db
def calculate_ma_timing(model_id: int, trade_date: str, db: Session = None):
    """基于移动平均线的择时信号"""
    # 获取模型配置
    config = get_timing_config(model_id, db=db)
    if not config or config.config_type != "ma_timing":
        return None

    # 获取配置参数
    params = config.config_params or {}
    ma_window = params.get("ma_window", 120)
    below_ma_exposure = params.get("below_ma_exposure", 0.5)

    # 获取基准指数数据（示例：沪深300）
    index_data = get_index_daily("000300.SH", trade_date, trade_date, db=db)
    if not index_data:
        return None

    # 获取历史数据计算移动平均线
    hist_data = get_index_daily("000300.SH",
                             f"{int(trade_date[:4])-1}-{trade_date[5:7]}-{trade_date[8:10]}",
                             trade_date, db=db)
    if not hist_data or len(hist_data) < ma_window:
        return None

    # 计算移动平均线
    closes = [d.close for d in hist_data[-ma_window:]]
    ma = np.mean(closes)
    current_close = index_data[0].close

    # 生成信号
    if current_close > ma:
        signal_type = "long"
        exposure = 1.0
    else:
        signal_type = "short"
        exposure = below_ma_exposure

    return TimingSignalCreate(
        model_id=model_id,
        trade_date=trade_date,
        signal_type=signal_type,
        exposure=exposure
    )

@with_db
def calculate_breadth_timing(model_id: int, trade_date: str, db: Session = None):
    """基于市场宽度的择时信号"""
    # 获取模型配置
    config = get_timing_config(model_id, db=db)
    if not config or config.config_type != "breadth_timing":
        return None

    # 获取市场宽度数据（示例）
    # 这里需要实现市场宽度的计算逻辑
    breadth = 0.75  # 模拟值
    threshold = config.config_params.get("breadth_threshold", 0.7)

    # 生成信号
    if breadth > threshold:
        signal_type = "long"
        exposure = 1.0
    else:
        signal_type = "short"
        exposure = 0.5

    return TimingSignalCreate(
        model_id=model_id,
        trade_date=trade_date,
        signal_type=signal_type,
        exposure=exposure
    )

@with_db
def calculate_volatility_timing(model_id: int, trade_date: str, db: Session = None):
    """基于波动率的择时信号"""
    # 获取模型配置
    config = get_timing_config(model_id, db=db)
    if not config or config.config_type != "volatility_timing":
        return None

    # 获取波动率数据（示例）
    # 这里需要实现波动率的计算逻辑
    volatility = 0.015  # 模拟值
    threshold = config.config_params.get("volatility_threshold", 0.02)

    # 生成信号
    if volatility < threshold:
        signal_type = "long"
        exposure = 1.0
    else:
        signal_type = "short"
        exposure = 0.3

    return TimingSignalCreate(
        model_id=model_id,
        trade_date=trade_date,
        signal_type=signal_type,
        exposure=exposure
    )
