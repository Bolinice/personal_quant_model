#!/usr/bin/env python
"""
端到端集成测试
验证完整的数据流：数据同步 → 因子计算 → 回测 → 结果展示
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from app.core.logging import logger
from app.db.base import SessionLocal
from app.models.market import StockDaily, StockBasic
from app.models.factors import Factor, FactorValue
from app.models.backtests import Backtest
from app.services.data_sync_service import DataSyncService
from app.core.config import settings


def test_database_connection():
    """测试1: 数据库连接"""
    print("\n" + "="*60)
    print("测试1: 数据库连接")
    print("="*60)

    try:
        db = SessionLocal()
        result = db.execute("SELECT 1").scalar()
        assert result == 1

        # 检查关键表
        tables = ['stock_basic', 'stock_daily', 'factors', 'backtests']
        for table in tables:
            count = db.execute(f"SELECT COUNT(*) FROM {table}").scalar()
            print(f"✓ {table}: {count} 条记录")

        db.close()
        print("\n✅ 数据库连接测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 数据库连接失败: {e}")
        return False


def test_data_availability():
    """测试2: 数据可用性"""
    print("\n" + "="*60)
    print("测试2: 数据可用性检查")
    print("="*60)

    db = SessionLocal()
    try:
        # 检查股票基础数据
        stock_count = db.query(StockBasic).count()
        print(f"股票数量: {stock_count}")

        if stock_count == 0:
            print("⚠️  股票基础数据为空，尝试同步...")
            service = DataSyncService(
                primary_source=settings.PRIMARY_DATA_SOURCE,
                tushare_token=settings.TUSHARE_TOKEN,
                tushare_proxy_url=settings.TUSHARE_PROXY_URL
            )
            count = service.sync_stock_basic()
            print(f"✓ 同步了 {count} 只股票")
            stock_count = count

        # 检查日线数据
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        daily_count = db.query(StockDaily).filter(
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).count()

        print(f"近30日日线数据: {daily_count} 条")

        if daily_count < 1000:
            print("⚠️  日线数据不足，建议运行: python scripts/sync_data.py")

        # 检查因子数据
        factor_count = db.query(Factor).count()
        print(f"因子数量: {factor_count}")

        factor_value_count = db.query(FactorValue).count()
        print(f"因子值数量: {factor_value_count}")

        # 检查回测数据
        backtest_count = db.query(Backtest).count()
        print(f"回测数量: {backtest_count}")

        success = stock_count > 0 and daily_count > 0
        if success:
            print("\n✅ 数据可用性检查通过")
        else:
            print("\n⚠️  数据不足，部分功能可能无法使用")

        return success

    except Exception as e:
        print(f"\n❌ 数据可用性检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_factor_calculation():
    """测试3: 因子计算"""
    print("\n" + "="*60)
    print("测试3: 因子计算流程")
    print("="*60)

    try:
        from app.core.alpha_modules import PriceModule
        from app.core.factor_preprocess import FactorPreprocessor
        import pandas as pd

        db = SessionLocal()

        # 获取测试数据
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=60)

        rows = db.query(StockDaily).filter(
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).limit(1000).all()

        if len(rows) < 100:
            print("⚠️  数据量不足，跳过因子计算测试")
            db.close()
            return False

        # 转换为DataFrame
        df = pd.DataFrame([{
            'ts_code': r.ts_code,
            'trade_date': r.trade_date,
            'close': float(r.close) if r.close else None,
            'open': float(r.open) if r.open else None,
            'high': float(r.high) if r.high else None,
            'low': float(r.low) if r.low else None,
            'vol': float(r.vol) if r.vol else None,
        } for r in rows])

        print(f"测试数据: {len(df)} 条记录")

        # 计算价格因子
        price_module = PriceModule()
        factors = price_module.calculate(df)

        print(f"✓ 计算了 {len(factors.columns)} 个价格因子")
        print(f"  因子列表: {list(factors.columns)[:5]}...")

        # 测试预处理
        preprocessor = FactorPreprocessor()
        processed = preprocessor.preprocess_dataframe(
            factors,
            factor_cols=factors.columns.tolist(),
            method='mad',
            winsorize_method='mad',
            standardize_method='zscore'
        )

        print(f"✓ 因子预处理完成")
        print(f"  处理后数据形状: {processed.shape}")

        db.close()
        print("\n✅ 因子计算测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 因子计算测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backtest_engine():
    """测试4: 回测引擎"""
    print("\n" + "="*60)
    print("测试4: 回测引擎")
    print("="*60)

    try:
        from app.core.backtest_engine import BacktestEngine, BacktestConfig
        import pandas as pd

        db = SessionLocal()

        # 获取测试数据
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)

        rows = db.query(StockDaily).filter(
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).limit(500).all()

        if len(rows) < 100:
            print("⚠️  数据量不足，跳过回测测试")
            db.close()
            return False

        # 准备价格数据
        price_df = pd.DataFrame([{
            'ts_code': r.ts_code,
            'trade_date': r.trade_date,
            'close': float(r.close) if r.close else None,
            'open': float(r.open) if r.open else None,
            'high': float(r.high) if r.high else None,
            'low': float(r.low) if r.low else None,
            'vol': float(r.vol) if r.vol else None,
        } for r in rows])

        # 生成简单的信号（动量策略）
        price_df = price_df.sort_values(['ts_code', 'trade_date'])
        price_df['return_20d'] = price_df.groupby('ts_code')['close'].pct_change(20)

        signal_df = price_df[['ts_code', 'trade_date', 'return_20d']].copy()
        signal_df = signal_df.dropna()

        if len(signal_df) < 50:
            print("⚠️  信号数据不足，跳过回测测试")
            db.close()
            return False

        print(f"测试数据: {len(price_df)} 条价格记录")
        print(f"信号数据: {len(signal_df)} 条")

        # 配置回测
        config = BacktestConfig(
            initial_capital=1_000_000,
            commission_rate=0.0003,
            stamp_tax_rate=0.001,
            slippage_rate=0.001,
        )

        # 运行回测
        engine = BacktestEngine(config)
        result = engine.run(
            signal_df=signal_df,
            price_df=price_df,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            holding_count=10,
            rebalance_freq='weekly'
        )

        print(f"\n回测结果:")
        print(f"  总收益率: {result.total_return:.2%}")
        print(f"  年化收益率: {result.annual_return:.2%}")
        print(f"  夏普比率: {result.sharpe_ratio:.2f}")
        print(f"  最大回撤: {result.max_drawdown:.2%}")
        print(f"  交易次数: {result.trade_count}")

        db.close()
        print("\n✅ 回测引擎测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 回测引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """测试5: API端点"""
    print("\n" + "="*60)
    print("测试5: API端点可用性")
    print("="*60)

    try:
        import requests

        base_url = "http://localhost:8000"

        # 测试健康检查
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            if resp.status_code == 200:
                print("✓ 健康检查端点正常")
            else:
                print(f"⚠️  健康检查返回 {resp.status_code}")
        except requests.exceptions.ConnectionError:
            print("⚠️  API服务未启动，跳过API测试")
            print("   提示: 运行 uvicorn app.main:app --reload")
            return False

        # 测试公开端点
        endpoints = [
            ("/api/v1/factors", "因子列表"),
            ("/api/v1/strategies", "策略列表"),
        ]

        for path, name in endpoints:
            try:
                resp = requests.get(f"{base_url}{path}", timeout=5)
                if resp.status_code in [200, 401]:  # 401表示需要认证但端点存在
                    print(f"✓ {name} 端点正常")
                else:
                    print(f"⚠️  {name} 返回 {resp.status_code}")
            except Exception as e:
                print(f"✗ {name} 失败: {e}")

        print("\n✅ API端点测试完成")
        return True

    except Exception as e:
        print(f"\n❌ API端点测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  A股多因子增强策略平台 - 端到端测试")
    print("="*60)

    results = {}

    # 运行测试
    results['数据库连接'] = test_database_connection()
    results['数据可用性'] = test_data_availability()
    results['因子计算'] = test_factor_calculation()
    results['回测引擎'] = test_backtest_engine()
    results['API端点'] = test_api_endpoints()

    # 汇总结果
    print("\n" + "="*60)
    print("  测试结果汇总")
    print("="*60)

    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")

    total = len(results)
    passed = sum(results.values())

    print(f"\n总计: {passed}/{total} 项测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！系统运行正常。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 项测试失败，请检查相关模块。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
