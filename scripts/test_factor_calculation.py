"""
测试因子计算功能
验证FactorCalculator能否正确从数据库读取数据并计算因子
"""

import sys
from datetime import date, datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.factor_calculator import FACTOR_GROUPS, FactorCalculator


def test_factor_calculation():
    """测试因子计算"""
    print("=" * 80)
    print("因子计算功能测试")
    print("=" * 80)

    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 1. 获取一些测试股票代码
        print("\n1. 获取测试股票代码...")
        result = db.execute(
            text(
                """
            SELECT DISTINCT ts_code
            FROM stock_daily
            WHERE trade_date >= '2026-04-01'
            LIMIT 5
        """
            )
        )
        test_stocks = [row[0] for row in result]
        print(f"   测试股票: {test_stocks}")

        # 2. 设置测试日期
        trade_date = date(2026, 4, 17)
        print(f"\n2. 测试日期: {trade_date}")

        # 3. 初始化因子计算器
        print("\n3. 初始化因子计算器...")
        calculator = FactorCalculator()

        # 4. 测试各个因子组
        print("\n4. 测试因子组计算:")
        print("-" * 80)

        test_groups = ["valuation", "quality", "growth", "momentum", "volatility"]

        for group_key in test_groups:
            if group_key not in FACTOR_GROUPS:
                continue

            print(f"\n   [{group_key}] {FACTOR_GROUPS[group_key]['name']}")
            print(f"   因子列表: {FACTOR_GROUPS[group_key]['factors']}")

            # 获取数据
            if group_key in ["valuation", "quality", "growth"]:
                # 财务因子需要财务数据
                financial_data = db.execute(
                    text(
                        """
                    SELECT * FROM stock_financial
                    WHERE ts_code = :ts_code
                    AND ann_date <= :trade_date
                    ORDER BY ann_date DESC
                    LIMIT 10
                """
                    ),
                    {"ts_code": test_stocks[0], "trade_date": trade_date},
                ).fetchall()

                if financial_data:
                    print(f"   ✅ 找到 {len(financial_data)} 条财务数据")
                else:
                    print(f"   ⚠️  未找到财务数据")

            elif group_key in ["momentum", "volatility"]:
                # 价格因子需要行情数据
                price_data = db.execute(
                    text(
                        """
                    SELECT * FROM stock_daily
                    WHERE ts_code = :ts_code
                    AND trade_date <= :trade_date
                    ORDER BY trade_date DESC
                    LIMIT 252
                """
                    ),
                    {"ts_code": test_stocks[0], "trade_date": trade_date},
                ).fetchall()

                if price_data:
                    print(f"   ✅ 找到 {len(price_data)} 条行情数据")
                else:
                    print(f"   ⚠️  未找到行情数据")

        # 5. 测试单个股票的因子计算
        print("\n5. 测试单个股票完整因子计算:")
        print("-" * 80)
        test_stock = test_stocks[0]
        print(f"   股票代码: {test_stock}")

        # 获取价格数据
        price_query = text(
            """
            SELECT trade_date, open, high, low, close, vol, amount,
                   pct_chg, turnover_rate
            FROM stock_daily
            WHERE ts_code = :ts_code
            AND trade_date <= :trade_date
            ORDER BY trade_date DESC
            LIMIT 252
        """
        )
        price_result = db.execute(price_query, {"ts_code": test_stock, "trade_date": trade_date})
        price_data = price_result.fetchall()

        if price_data:
            print(f"   ✅ 价格数据: {len(price_data)} 条")
            print(f"   日期范围: {price_data[-1][0]} ~ {price_data[0][0]}")

            # 转换为DataFrame格式
            import pandas as pd

            price_df = pd.DataFrame(
                price_data,
                columns=[
                    "trade_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "vol",
                    "amount",
                    "pct_chg",
                    "turnover_rate",
                ],
            )
            price_df["ts_code"] = test_stock

            # 计算动量因子
            print("\n   计算动量因子...")
            momentum_factors = calculator.calc_momentum_factors(price_df)
            print(f"   结果: {momentum_factors.to_dict('records')[0] if not momentum_factors.empty else 'Empty'}")

            # 计算波动率因子
            print("\n   计算波动率因子...")
            volatility_factors = calculator.calc_volatility_factors(price_df)
            print(
                f"   结果: {volatility_factors.to_dict('records')[0] if not volatility_factors.empty else 'Empty'}"
            )

        # 获取财务数据
        financial_query = text(
            """
            SELECT * FROM stock_financial
            WHERE ts_code = :ts_code
            AND ann_date <= :trade_date
            ORDER BY ann_date DESC
            LIMIT 10
        """
        )
        financial_result = db.execute(
            financial_query, {"ts_code": test_stock, "trade_date": trade_date}
        )
        financial_data = financial_result.fetchall()

        if financial_data:
            print(f"\n   ✅ 财务数据: {len(financial_data)} 条")

            # 转换为DataFrame
            import pandas as pd

            financial_df = pd.DataFrame(financial_data, columns=financial_result.keys())

            # 计算估值因子
            print("\n   计算估值因子...")
            valuation_factors = calculator.calc_valuation_factors(financial_df, trade_date)
            print(
                f"   结果: {valuation_factors.to_dict('records')[0] if not valuation_factors.empty else 'Empty'}"
            )

        # 6. 统计总结
        print("\n" + "=" * 80)
        print("测试总结:")
        print("=" * 80)
        print(f"✅ 测试股票数量: {len(test_stocks)}")
        print(f"✅ 测试日期: {trade_date}")
        print(f"✅ 可用因子组: {len(FACTOR_GROUPS)}")
        print(f"✅ 数据库连接正常")
        print(f"✅ 因子计算器初始化成功")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    test_factor_calculation()
