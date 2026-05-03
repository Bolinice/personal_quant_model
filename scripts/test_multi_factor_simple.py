"""
简化的多因子模型测试
验证核心组件是否正常工作
"""

import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.multi_factor_model import MultiFactorModel


def test_multi_factor_model_simple():
    """简化测试：验证模型初始化和基本功能"""
    print("=" * 80)
    print("多因子选股模型 - 简化测试")
    print("=" * 80)

    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 1. 获取测试股票
        print("\n[1] 获取测试股票...")
        query = text("""
            SELECT DISTINCT ts_code
            FROM stock_daily
            WHERE trade_date >= '2026-04-01'
            LIMIT 20
        """)
        result = db.execute(query)
        ts_codes = [row[0] for row in result]
        print(f"   ✓ 获取到 {len(ts_codes)} 只股票: {ts_codes[:5]}...")

        # 2. 获取最新交易日
        query = text("SELECT MAX(trade_date) FROM stock_daily")
        trade_date = db.execute(query).scalar()
        print(f"   ✓ 交易日期: {trade_date}")

        # 3. 初始化模型
        print("\n[2] 初始化多因子模型...")
        model = MultiFactorModel(
            db=db,
            factor_groups=["valuation", "quality"],  # 只用2个因子组测试
            weighting_method="equal",
            neutralize_industry=False,  # 简化测试，不做中性化
            neutralize_market_cap=False,
        )
        print(f"   ✓ 模型初始化成功")
        print(f"   ✓ 使用因子组: {model.factor_groups}")

        # 4. 测试完整流程
        print("\n[3] 运行完整流程...")
        result = model.run(
            ts_codes=ts_codes,
            trade_date=trade_date,
            total_value=1000000.0,
            current_holdings={},
            top_n=10,
            exclude_list=[],
        )

        print(f"   ✓ 流程完成")
        print(f"   ✓ 目标持仓: {len(result.get('target_holdings', {}))} 只")
        print(f"   ✓ 交易数量: {len(result.get('trades', []))} 笔")

        # 5. 显示结果
        if result.get('target_holdings'):
            print("\n[4] 持仓详情（前5只）:")
            for i, (ts_code, shares) in enumerate(list(result['target_holdings'].items())[:5], 1):
                print(f"   {i}. {ts_code}: {shares:.0f} 股")

        print("\n" + "=" * 80)
        print("✓ 测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_multi_factor_model_simple()
