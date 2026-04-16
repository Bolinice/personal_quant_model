"""
示例数据生成脚本
生成测试用的市场数据、因子数据等
"""
import sys
sys.path.insert(0, '.')

import random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, Base, engine
from app.models.market import StockDaily, IndexDaily, TradingCalendar, StockBasic, StockIndustry
from app.models.factors import Factor, FactorValue
from app.models.models import Model, ModelFactorWeight, ModelScore
from app.core.logging import logger


def generate_trading_calendar(start_date: str, end_date: str):
    """生成交易日历"""
    db = SessionLocal()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        current = start
        while current <= end:
            # 简化：周一到周五为交易日
            is_open = current.weekday() < 5

            calendar = TradingCalendar(
                exchange='SSE',
                cal_date=current.date(),
                is_open=is_open,
                pretrade_date=current.date() - timedelta(days=1) if is_open else None
            )
            db.add(calendar)
            current += timedelta(days=1)

        db.commit()
        logger.info(f"Generated trading calendar from {start_date} to {end_date}")

    except Exception as e:
        logger.error(f"Error generating calendar: {e}")
        db.rollback()
    finally:
        db.close()


def generate_stock_basic(num_stocks: int = 100):
    """生成股票基础信息"""
    db = SessionLocal()
    try:
        boards = ['main', 'gem', 'star']
        industries = ['银行', '房地产', '医药生物', '食品饮料', '电子', '计算机', '传媒', '通信', '电气设备', '机械设备']

        for i in range(num_stocks):
            code = f"{600000 + i:06d}"
            ts_code = f"{code}.SH"

            stock = StockBasic(
                ts_code=ts_code,
                symbol=code,
                name=f"股票{i+1}",
                board=random.choice(boards),
                list_date=datetime(2020, 1, 1) - timedelta(days=random.randint(0, 1000)),
                status='L'
            )
            db.add(stock)

        db.commit()
        logger.info(f"Generated {num_stocks} stock basic info")

    except Exception as e:
        logger.error(f"Error generating stock basic: {e}")
        db.rollback()
    finally:
        db.close()


def generate_stock_daily(start_date: str, end_date: str, num_stocks: int = 100):
    """生成股票日线数据"""
    db = SessionLocal()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        # 获取交易日
        trading_days = db.query(TradingCalendar).filter(
            TradingCalendar.exchange == 'SSE',
            TradingCalendar.cal_date >= start.date(),
            TradingCalendar.cal_date <= end.date(),
            TradingCalendar.is_open == True
        ).all()

        trade_dates = [t.cal_date for t in trading_days]

        for i in range(num_stocks):
            code = f"{600000 + i:06d}"
            ts_code = f"{code}.SH"

            # 生成价格序列（随机游走）
            base_price = random.uniform(10, 100)
            prices = [base_price]

            for _ in range(len(trade_dates) - 1):
                change = random.gauss(0, 0.02)  # 日收益率
                new_price = prices[-1] * (1 + change)
                prices.append(max(new_price, 1))  # 价格不低于1

            for j, trade_date in enumerate(trade_dates):
                close = prices[j]
                open_price = close * (1 + random.gauss(0, 0.005))
                high = max(close, open_price) * (1 + abs(random.gauss(0, 0.01)))
                low = min(close, open_price) * (1 - abs(random.gauss(0, 0.01)))
                volume = random.uniform(1000000, 10000000)
                amount = volume * close
                pct_chg = ((prices[j] / prices[j-1]) - 1) * 100 if j > 0 else 0
                pre_close = prices[j-1] if j > 0 else close

                daily = StockDaily(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    pre_close=pre_close,
                    change=close - pre_close,
                    pct_chg=pct_chg,
                    vol=volume,
                    amount=amount
                )
                db.add(daily)

            if (i + 1) % 20 == 0:
                db.commit()
                logger.info(f"Generated daily data for {i + 1} stocks")

        db.commit()
        logger.info(f"Generated stock daily data for {num_stocks} stocks")

    except Exception as e:
        logger.error(f"Error generating stock daily: {e}")
        db.rollback()
    finally:
        db.close()


def generate_index_daily(start_date: str, end_date: str):
    """生成指数日线数据"""
    db = SessionLocal()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        trading_days = db.query(TradingCalendar).filter(
            TradingCalendar.exchange == 'SSE',
            TradingCalendar.cal_date >= start.date(),
            TradingCalendar.cal_date <= end.date(),
            TradingCalendar.is_open == True
        ).all()

        trade_dates = [t.cal_date for t in trading_days]

        indices = [
            ('000300.SH', '沪深300'),
            ('000905.SH', '中证500'),
            ('000852.SH', '中证1000'),
        ]

        for index_code, index_name in indices:
            base_price = 4000 if '300' in index_code else 5000 if '500' in index_code else 6000
            prices = [base_price]

            for _ in range(len(trade_dates) - 1):
                change = random.gauss(0.0002, 0.015)  # 指数日收益率
                new_price = prices[-1] * (1 + change)
                prices.append(max(new_price, 1000))

            for j, trade_date in enumerate(trade_dates):
                close = prices[j]
                open_price = close * (1 + random.gauss(0, 0.003))
                high = max(close, open_price) * (1 + abs(random.gauss(0, 0.005)))
                low = min(close, open_price) * (1 - abs(random.gauss(0, 0.005)))
                volume = random.uniform(100000000, 500000000)
                amount = volume * close
                pct_chg = ((prices[j] / prices[j-1]) - 1) * 100 if j > 0 else 0
                pre_close = prices[j-1] if j > 0 else close

                daily = IndexDaily(
                    ts_code=index_code,
                    trade_date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    pre_close=pre_close,
                    change=close - pre_close,
                    pct_chg=pct_chg,
                    vol=volume,
                    amount=amount
                )
                db.add(daily)

        db.commit()
        logger.info(f"Generated index daily data for {len(indices)} indices")

    except Exception as e:
        logger.error(f"Error generating index daily: {e}")
        db.rollback()
    finally:
        db.close()


def generate_factor_values(trade_date: str, num_stocks: int = 100):
    """生成因子值数据"""
    db = SessionLocal()
    try:
        factors = db.query(Factor).all()

        for factor in factors:
            for i in range(num_stocks):
                code = f"{600000 + i:06d}"
                ts_code = f"{code}.SH"

                # 根据因子类型生成不同的值
                if factor.category == 'quality':
                    value = random.gauss(0.1, 0.05)
                elif factor.category == 'valuation':
                    value = random.gauss(20, 15)
                elif factor.category == 'momentum':
                    value = random.gauss(0, 0.3)
                elif factor.category == 'growth':
                    value = random.gauss(0.15, 0.1)
                elif factor.category == 'risk':
                    value = random.gauss(0.25, 0.1)
                else:
                    value = random.gauss(0, 1)

                fv = FactorValue(
                    factor_id=factor.id,
                    trade_date=trade_date,
                    security_id=ts_code,
                    value=value,
                    is_valid=True
                )
                db.add(fv)

        db.commit()
        logger.info(f"Generated factor values for {len(factors)} factors on {trade_date}")

    except Exception as e:
        logger.error(f"Error generating factor values: {e}")
        db.rollback()
    finally:
        db.close()


def generate_model_and_scores(trade_date: str, num_stocks: int = 100):
    """生成模型和评分数据"""
    db = SessionLocal()
    try:
        # 创建模型
        model = Model(
            model_code='MULTI_FACTOR_001',
            model_name='多因子增强模型V1',
            pool_id=1,
            rebalance_frequency='weekly',
            hold_count=50,
            weighting_method='equal',
            timing_enabled=True,
            is_active=True
        )
        db.add(model)
        db.flush()

        # 设置因子权重
        factors = db.query(Factor).limit(5).all()
        for i, factor in enumerate(factors):
            weight = ModelFactorWeight(
                model_id=model.id,
                factor_id=factor.id,
                weight=0.2  # 等权
            )
            db.add(weight)

        # 生成评分
        for i in range(num_stocks):
            code = f"{600000 + i:06d}"
            ts_code = f"{code}.SH"

            score = ModelScore(
                model_id=model.id,
                trade_date=trade_date,
                security_id=ts_code,
                total_score=random.gauss(0, 1)
            )
            db.add(score)

        db.commit()
        logger.info(f"Generated model and scores for {trade_date}")

    except Exception as e:
        logger.error(f"Error generating model and scores: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """主函数"""
    print("=" * 50)
    print("开始生成示例数据...")
    print("=" * 50)

    # 配置
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    num_stocks = 100

    # 1. 生成交易日历
    print("\n1. 生成交易日历...")
    generate_trading_calendar(start_date, end_date)

    # 2. 生成股票基础信息
    print("\n2. 生成股票基础信息...")
    generate_stock_basic(num_stocks)

    # 3. 生成股票日线数据
    print("\n3. 生成股票日线数据...")
    generate_stock_daily(start_date, end_date, num_stocks)

    # 4. 生成指数日线数据
    print("\n4. 生成指数日线数据...")
    generate_index_daily(start_date, end_date)

    # 5. 生成因子值
    print("\n5. 生成因子值...")
    generate_factor_values("2023-12-29", num_stocks)

    # 6. 生成模型和评分
    print("\n6. 生成模型和评分...")
    generate_model_and_scores("2023-12-29", num_stocks)

    print("\n" + "=" * 50)
    print("示例数据生成完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
