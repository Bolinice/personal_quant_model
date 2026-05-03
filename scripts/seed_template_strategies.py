"""
添加模板策略到数据库
"""
import sys
sys.path.insert(0, '.')

from app.db.base import SessionLocal
from app.models.models import Model
from app.models.backtests import Backtest, BacktestResult
from app.core.logging import logger
import json
from datetime import datetime


def create_template_strategies():
    """创建模板策略"""
    db = SessionLocal()
    try:
        # 模板策略1: 价值成长组合
        strategy1 = db.query(Model).filter(Model.model_code == "TEMPLATE_VALUE_GROWTH").first()
        if not strategy1:
            strategy1 = Model(
                model_code="TEMPLATE_VALUE_GROWTH",
                model_name="价值成长组合",
                model_type="multi_factor",
                description="结合估值和成长因子，选择低估值高成长的优质股票。适合中长期投资者。",
                version="1.0.0",
                status="active",
                factor_ids=json.dumps(["PE_TTM", "PB", "REVENUE_GROWTH", "PROFIT_GROWTH"]),
                factor_weights=json.dumps({"PE_TTM": 0.3, "PB": 0.2, "REVENUE_GROWTH": 0.25, "PROFIT_GROWTH": 0.25}),
                model_config=json.dumps({
                    "universe": "hs300",
                    "top_n": 20,
                    "rebalance_freq": "monthly",
                    "factors": ["valuation", "growth"]
                }),
                ic_mean=0.045,
                ic_ir=0.68,
                rank_ic_mean=0.052,
                rank_ic_ir=0.75,
                turnover=0.15,
                is_default=True
            )
            db.add(strategy1)
            db.flush()

            # 添加回测任务
            backtest1 = Backtest(
                model_id=strategy1.id,
                job_name="2024年回测",
                benchmark_code="000300.SH",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=1000000.0,
                rebalance_freq="monthly",
                holding_count=20,
                status="success"
            )
            db.add(backtest1)
            db.flush()

            # 添加回测结果
            result1 = BacktestResult(
                backtest_id=backtest1.id,
                total_return=0.1250,
                annual_return=0.1971,
                benchmark_return=0.1144,
                excess_return=0.0106,
                annual_excess_return=0.0827,
                max_drawdown=-0.1718,
                volatility=0.28,
                sharpe=0.68,
                information_ratio=0.55,
                turnover_rate=1.5248,
                win_rate=0.4817
            )
            db.add(result1)
            logger.info("Created template strategy: 价值成长组合")

        # 模板策略2: 质量动量组合
        strategy2 = db.query(Model).filter(Model.model_code == "TEMPLATE_QUALITY_MOMENTUM").first()
        if not strategy2:
            strategy2 = Model(
                model_code="TEMPLATE_QUALITY_MOMENTUM",
                model_name="质量动量组合",
                model_type="multi_factor",
                description="结合盈利质量和价格动量，捕捉高质量且趋势向上的股票。适合追求稳健收益的投资者。",
                version="1.0.0",
                status="active",
                factor_ids=json.dumps(["ROE", "ROA", "GROSS_MARGIN", "MOM_20D", "MOM_60D"]),
                factor_weights=json.dumps({"ROE": 0.25, "ROA": 0.2, "GROSS_MARGIN": 0.15, "MOM_20D": 0.2, "MOM_60D": 0.2}),
                model_config=json.dumps({
                    "universe": "hs300",
                    "top_n": 30,
                    "rebalance_freq": "monthly",
                    "factors": ["quality", "momentum"]
                }),
                ic_mean=0.038,
                ic_ir=0.62,
                rank_ic_mean=0.048,
                rank_ic_ir=0.71,
                turnover=0.18,
                is_default=True
            )
            db.add(strategy2)
            db.flush()

            # 添加回测任务
            backtest2 = Backtest(
                model_id=strategy2.id,
                job_name="2024年回测",
                benchmark_code="000300.SH",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=1000000.0,
                rebalance_freq="monthly",
                holding_count=30,
                status="success"
            )
            db.add(backtest2)
            db.flush()

            # 添加回测结果
            result2 = BacktestResult(
                backtest_id=backtest2.id,
                total_return=0.1080,
                annual_return=0.1702,
                benchmark_return=0.1144,
                excess_return=-0.0064,
                annual_excess_return=-0.0558,
                max_drawdown=-0.1523,
                volatility=0.32,
                sharpe=0.58,
                information_ratio=-0.12,
                turnover_rate=1.8234,
                win_rate=0.5167
            )
            db.add(result2)
            logger.info("Created template strategy: 质量动量组合")

        # 模板策略3: 低波红利组合
        strategy3 = db.query(Model).filter(Model.model_code == "TEMPLATE_LOW_VOL_DIVIDEND").first()
        if not strategy3:
            strategy3 = Model(
                model_code="TEMPLATE_LOW_VOL_DIVIDEND",
                model_name="低波红利组合",
                model_type="multi_factor",
                description="选择低波动率、高股息率的防御性股票。适合风险厌恶型投资者和震荡市场。",
                version="1.0.0",
                status="active",
                factor_ids=json.dumps(["VOL_20D", "VOL_60D", "PE_TTM", "PB"]),
                factor_weights=json.dumps({"VOL_20D": 0.3, "VOL_60D": 0.2, "PE_TTM": 0.25, "PB": 0.25}),
                model_config=json.dumps({
                    "universe": "hs300",
                    "top_n": 25,
                    "rebalance_freq": "quarterly",
                    "factors": ["risk", "valuation"]
                }),
                ic_mean=0.032,
                ic_ir=0.55,
                rank_ic_mean=0.041,
                rank_ic_ir=0.64,
                turnover=0.08,
                is_default=True
            )
            db.add(strategy3)
            db.flush()

            # 添加回测任务
            backtest3 = Backtest(
                model_id=strategy3.id,
                job_name="2024年回测",
                benchmark_code="000300.SH",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=1000000.0,
                rebalance_freq="monthly",
                holding_count=25,
                status="success"
            )
            db.add(backtest3)
            db.flush()

            # 添加回测结果
            result3 = BacktestResult(
                backtest_id=backtest3.id,
                total_return=0.0950,
                annual_return=0.1497,
                benchmark_return=0.1144,
                excess_return=-0.0194,
                annual_excess_return=-0.0353,
                max_drawdown=-0.1245,
                volatility=0.21,
                sharpe=0.72,
                information_ratio=-0.38,
                turnover_rate=0.8156,
                win_rate=0.5833
            )
            db.add(result3)
            logger.info("Created template strategy: 低波红利组合")

        db.commit()
        logger.info("Template strategies created successfully!")

    except Exception as e:
        logger.error(f"Error creating template strategies: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_template_strategies()
    print("模板策略创建完成!")
