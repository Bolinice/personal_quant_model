"""
测试多因子选股模型完整流程
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.multi_factor_model import FactorWeightingMethod, MultiFactorModel


def test_multi_factor_model():
    """测试多因子模型完整流程"""
    print("=" * 80)
    print("多因子选股模型测试")
    print("=" * 80)

    # 1. 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 2. 获取测试数据
        print("\n[1] 获取测试股票池...")
        query = text("""
            SELECT DISTINCT ts_code
            FROM stock_daily
            WHERE trade_date >= :start_date
            AND ts_code LIKE '%.SH' OR ts_code LIKE '%.SZ'
            ORDER BY ts_code
            LIMIT 100
        """)
        start_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")
        result = db.execute(query, {"start_date": start_date})
        ts_codes = [row[0] for row in result]
        print(f"   ✓ 获取到 {len(ts_codes)} 只股票")

        # 3. 设置交易日期（使用最近的交易日）
        query = text("""
            SELECT MAX(trade_date) as latest_date
            FROM stock_daily
        """)
        result = db.execute(query)
        trade_date = result.scalar()
        print(f"   ✓ 交易日期: {trade_date}")

        # 4. 创建多因子模型实例
        print("\n[2] 初始化多因子模型...")
        model = MultiFactorModel(
            db=db,
            factor_groups=["valuation", "quality", "growth", "momentum"],
            weighting_method=FactorWeightingMethod.EQUAL,
            neutralize_industry=False,  # 暂时关闭中性化
            neutralize_market_cap=False,
        )
        print(f"   ✓ 可用因子组: {len(model.factor_groups)} 个")

        # 5. 运行完整流程
        print("\n[3] 运行完整流程...")
        result = model.run(
            ts_codes=ts_codes,
            trade_date=trade_date,
            total_value=1000000.0,  # 100万
            current_holdings={},
            top_n=30,
            exclude_list=[],
        )

        print(f"   ✓ 流程完成")
        print(f"   ✓ 目标持仓: {len(result.get('target_holdings', {}))} 只")
        print(f"   ✓ 交易数量: {len(result.get('trades', []))} 笔")

        # 6. 显示部分持仓
        if result.get('target_holdings'):
            print("\n[4] 持仓详情（前10只）:")
            for i, (ts_code, shares) in enumerate(list(result['target_holdings'].items())[:10], 1):
                print(f"   {i}. {ts_code}: {shares:.0f} 股")

        # 7. 显示部分交易
        if result.get('trades'):
            print("\n[5] 交易详情（前5笔）:")
            for i, trade in enumerate(result['trades'][:5], 1):
                print(f"   {i}. {trade['action'].upper()} {trade['ts_code']}: {trade['shares']:.0f}股 @ ¥{trade['price']:.2f}")

        print("\n" + "=" * 80)
        print("✓ 多因子模型测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_multi_factor_model()
