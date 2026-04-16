"""
数据库初始化脚本
创建所有必要的表结构
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from app.db.base import Base, engine
from app.core.config import settings
from app.core.logging import logger

# 导入所有模型以确保它们被注册
from app.models.user import User
from app.models.securities import Security
from app.models.stock_pools import StockPool, StockPoolSnapshot
from app.models.factors import Factor, FactorValue, FactorAnalysis, FactorResult
from app.models.models import Model, ModelFactorWeight, ModelScore
from app.models.timing import TimingModel, TimingSignal, TimingConfig
from app.models.portfolios import Portfolio, PortfolioPosition, RebalanceRecord
from app.models.backtests import Backtest, BacktestResult, BacktestTrade
from app.models.simulated_portfolios import SimulatedPortfolio, SimulatedPortfolioPosition, SimulatedPortfolioNav
from app.models.products import Product
from app.models.subscriptions import Subscription
from app.models.reports import Report, ReportTemplate, ReportSchedule
from app.models.task_logs import TaskLog
from app.models.alert_logs import AlertLog
from app.models.market import StockDaily, IndexDaily, TradingCalendar, StockFinancial, StockIndustry, StockBasic


def init_database(drop_existing: bool = False):
    """
    初始化数据库

    Args:
        drop_existing: 是否删除现有表
    """
    if drop_existing:
        logger.info("Dropping existing tables...")
        Base.metadata.drop_all(bind=engine)

    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully!")


def create_default_data():
    """创建默认数据"""
    from app.db.base import SessionLocal
    import hashlib

    db = SessionLocal()
    try:
        # 创建默认管理员用户
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            # 使用简单的 SHA256 哈希作为默认密码
            hashed_password = hashlib.sha256("admin123".encode()).hexdigest()
            admin = User(
                username="admin",
                email="admin@example.com",
                real_name="系统管理员",
                hashed_password=hashed_password,
                role="admin"
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin user created: admin / admin123")

        # 创建默认因子
        default_factors = [
            {"factor_code": "ROE", "factor_name": "净资产收益率", "category": "quality", "direction": "desc", "calc_expression": "net_profit / equity", "description": "ROE = 净利润 / 净资产"},
            {"factor_code": "ROA", "factor_name": "总资产收益率", "category": "quality", "direction": "desc", "calc_expression": "net_profit / total_assets", "description": "ROA = 净利润 / 总资产"},
            {"factor_code": "GROSS_MARGIN", "factor_name": "毛利率", "category": "quality", "direction": "desc", "calc_expression": "(revenue - cost) / revenue", "description": "毛利率 = (营收 - 成本) / 营收"},
            {"factor_code": "NET_MARGIN", "factor_name": "净利率", "category": "quality", "direction": "desc", "calc_expression": "net_profit / revenue", "description": "净利率 = 净利润 / 营收"},
            {"factor_code": "PE_TTM", "factor_name": "市盈率TTM", "category": "valuation", "direction": "asc", "calc_expression": "market_cap / net_profit_ttm", "description": "PE(TTM) = 市值 / 过去12个月净利润"},
            {"factor_code": "PB", "factor_name": "市净率", "category": "valuation", "direction": "asc", "calc_expression": "market_cap / equity", "description": "PB = 市值 / 净资产"},
            {"factor_code": "PS_TTM", "factor_name": "市销率TTM", "category": "valuation", "direction": "asc", "calc_expression": "market_cap / revenue_ttm", "description": "PS(TTM) = 市值 / 过去12个月营收"},
            {"factor_code": "MOM_20D", "factor_name": "20日动量", "category": "momentum", "direction": "desc", "calc_expression": "close / close_20d - 1", "description": "20日收益率"},
            {"factor_code": "MOM_60D", "factor_name": "60日动量", "category": "momentum", "direction": "desc", "calc_expression": "close / close_60d - 1", "description": "60日收益率"},
            {"factor_code": "MOM_120D", "factor_name": "120日动量", "category": "momentum", "direction": "desc", "calc_expression": "close / close_120d - 1", "description": "120日收益率"},
            {"factor_code": "REVENUE_GROWTH", "factor_name": "营收增长率", "category": "growth", "direction": "desc", "calc_expression": "(revenue - revenue_yoy) / revenue_yoy", "description": "营收同比增速"},
            {"factor_code": "PROFIT_GROWTH", "factor_name": "净利润增长率", "category": "growth", "direction": "desc", "calc_expression": "(net_profit - net_profit_yoy) / net_profit_yoy", "description": "净利润同比增速"},
            {"factor_code": "VOL_20D", "factor_name": "20日波动率", "category": "risk", "direction": "asc", "calc_expression": "std(daily_return_20d) * sqrt(252)", "description": "20日年化波动率"},
            {"factor_code": "VOL_60D", "factor_name": "60日波动率", "category": "risk", "direction": "asc", "calc_expression": "std(daily_return_60d) * sqrt(252)", "description": "60日年化波动率"},
            {"factor_code": "TURNOVER_20D", "factor_name": "20日换手率", "category": "liquidity", "direction": "asc", "calc_expression": "avg(turnover_rate_20d)", "description": "20日平均换手率"},
            {"factor_code": "AMOUNT_20D", "factor_name": "20日成交额", "category": "liquidity", "direction": "desc", "calc_expression": "avg(amount_20d)", "description": "20日平均成交额"},
        ]

        for factor_data in default_factors:
            existing = db.query(Factor).filter(Factor.factor_code == factor_data["factor_code"]).first()
            if not existing:
                factor = Factor(**factor_data)
                db.add(factor)

        db.commit()
        logger.info(f"Created {len(default_factors)} default factors")

        # 创建默认股票池
        default_pools = [
            {"pool_code": "HS300", "pool_name": "沪深300成分股", "description": "沪深300指数成分股"},
            {"pool_code": "ZZ500", "pool_name": "中证500成分股", "description": "中证500指数成分股"},
            {"pool_code": "ZZ1000", "pool_name": "中证1000成分股", "description": "中证1000指数成分股"},
            {"pool_code": "ALL_A", "pool_name": "全A股", "description": "全部A股股票"},
        ]

        for pool_data in default_pools:
            existing = db.query(StockPool).filter(StockPool.pool_code == pool_data["pool_code"]).first()
            if not existing:
                pool = StockPool(**pool_data)
                db.add(pool)

        db.commit()
        logger.info(f"Created {len(default_pools)} default stock pools")

    except Exception as e:
        logger.error(f"Error creating default data: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="数据库初始化")
    parser.add_argument("--drop", action="store_true", help="删除现有表后重建")
    parser.add_argument("--seed", action="store_true", help="创建默认数据")
    args = parser.parse_args()

    init_database(drop_existing=args.drop)

    if args.seed:
        create_default_data()

    print("数据库初始化完成!")
