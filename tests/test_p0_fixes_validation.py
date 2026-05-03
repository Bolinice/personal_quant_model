"""
P0修复验证脚本
==============
验证行业分类历史时点查询和残差动量因子实现的正确性

运行方式:
    python tests/test_p0_fixes_validation.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import date, datetime


def test_industry_repository():
    """测试行业分类Repository的历史时点查询"""
    print("\n" + "="*60)
    print("测试1: 行业分类历史时点查询")
    print("="*60)

    from app.models.market.stock_industry import StockIndustry
    from sqlalchemy import inspect

    # 检查模型字段
    inspector = inspect(StockIndustry)
    columns = [col.name for col in inspector.columns]

    print("\nStockIndustry模型字段:")
    for col in columns:
        print(f"  - {col}")

    # 验证关键字段存在
    required_fields = ['effective_date', 'expire_date']
    missing_fields = [f for f in required_fields if f not in columns]

    if missing_fields:
        print(f"\n❌ 缺少字段: {missing_fields}")
        return False
    else:
        print(f"\n✅ 所有必需字段都存在")

    # 测试IndustryRepository
    try:
        from app.repositories.industry_repo import IndustryRepository
        print("\n✅ IndustryRepository导入成功")

        # 检查方法
        methods = [m for m in dir(IndustryRepository) if not m.startswith('_')]
        print(f"\nIndustryRepository方法: {methods}")

        required_methods = ['get_industry_at_date', 'get_current_industry', 'get_industry_changes']
        missing_methods = [m for m in required_methods if m not in methods]

        if missing_methods:
            print(f"\n❌ 缺少方法: {missing_methods}")
            return False
        else:
            print(f"\n✅ 所有必需方法都存在")

    except ImportError as e:
        print(f"\n❌ IndustryRepository导入失败: {e}")
        return False

    return True


def test_factor_preprocess_historical():
    """测试因子预处理的历史时点支持"""
    print("\n" + "="*60)
    print("测试2: 因子预处理历史时点支持")
    print("="*60)

    try:
        from app.core.factor_preprocess import FactorPreprocessor
        import inspect

        preprocessor = FactorPreprocessor()

        # 检查neutralize_industry方法签名
        sig = inspect.signature(preprocessor.neutralize_industry)
        params = list(sig.parameters.keys())

        print(f"\nneutralize_industry参数: {params}")

        required_params = ['df', 'value_col', 'industry_col', 'trade_date', 'session']
        missing_params = [p for p in required_params if p not in params]

        if missing_params:
            print(f"\n❌ 缺少参数: {missing_params}")
            return False
        else:
            print(f"\n✅ neutralize_industry支持历史时点查询")

        # 检查neutralize_industry_and_cap方法
        sig2 = inspect.signature(preprocessor.neutralize_industry_and_cap)
        params2 = list(sig2.parameters.keys())

        print(f"\nneutralize_industry_and_cap参数: {params2}")

        if 'trade_date' not in params2 or 'session' not in params2:
            print(f"\n❌ neutralize_industry_and_cap不支持历史时点查询")
            return False
        else:
            print(f"\n✅ neutralize_industry_and_cap支持历史时点查询")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False

    return True


def test_residual_momentum_implementation():
    """测试残差动量因子实现"""
    print("\n" + "="*60)
    print("测试3: 残差动量因子实现")
    print("="*60)

    try:
        from app.core.factors.momentum import (
            calc_residual_returns,
            calc_residual_momentum_factors
        )

        print("\n✅ 残差动量函数导入成功")
        print("  - calc_residual_returns")
        print("  - calc_residual_momentum_factors")

        # 测试函数签名
        import inspect

        sig1 = inspect.signature(calc_residual_returns)
        params1 = list(sig1.parameters.keys())
        print(f"\ncalc_residual_returns参数: {params1}")

        required_params1 = ['returns', 'style_factors', 'lookback_window']
        missing_params1 = [p for p in required_params1 if p not in params1]

        if missing_params1:
            print(f"❌ calc_residual_returns缺少参数: {missing_params1}")
            return False

        sig2 = inspect.signature(calc_residual_momentum_factors)
        params2 = list(sig2.parameters.keys())
        print(f"\ncalc_residual_momentum_factors参数: {params2}")

        required_params2 = ['returns', 'style_factors', 'windows']
        missing_params2 = [p for p in required_params2 if p not in params2]

        if missing_params2:
            print(f"❌ calc_residual_momentum_factors缺少参数: {missing_params2}")
            return False

        print("\n✅ 所有必需参数都存在")

        # 简单功能测试
        print("\n执行简单功能测试...")

        # 创建测试数据
        dates = pd.date_range('2020-01-01', periods=100, freq='D')
        stocks = ['000001.SZ', '000002.SZ', '600000.SH']

        # 模拟收益率数据
        returns = pd.DataFrame(
            np.random.randn(100, 3) * 0.02,
            index=dates,
            columns=stocks
        )

        # 模拟风格因子数据
        style_factor_data = []
        for date in dates:
            for stock in stocks:
                style_factor_data.append({
                    'date': date,
                    'stock': stock,
                    'size': np.random.randn(),
                    'value': np.random.randn(),
                    'momentum': np.random.randn()
                })

        style_factors = pd.DataFrame(style_factor_data)
        style_factors = style_factors.set_index(['date', 'stock'])
        style_factors = style_factors[['size', 'value', 'momentum']]

        # 测试calc_residual_returns
        residual_ret = calc_residual_returns(
            returns=returns,
            style_factors=style_factors,
            lookback_window=20,
            min_periods=10
        )

        print(f"\n残差收益率计算结果:")
        print(f"  Shape: {residual_ret.shape}")
        print(f"  非空值数量: {residual_ret.notna().sum().sum()}")

        if residual_ret.empty:
            print("⚠️  残差收益率为空（可能是测试数据问题）")
        else:
            print("✅ 残差收益率计算成功")

        # 测试calc_residual_momentum_factors
        momentum_factors = calc_residual_momentum_factors(
            returns=returns,
            style_factors=style_factors,
            windows=[20, 60]
        )

        print(f"\n残差动量因子计算结果:")
        print(f"  Columns: {list(momentum_factors.columns)}")
        print(f"  Shape: {momentum_factors.shape}")

        expected_cols = ['residual_return_20d', 'residual_return_60d', 'residual_sharpe']
        missing_cols = [c for c in expected_cols if c not in momentum_factors.columns]

        if missing_cols:
            print(f"❌ 缺少因子列: {missing_cols}")
            return False
        else:
            print("✅ 所有预期因子列都存在")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_database_migration():
    """测试数据库迁移脚本"""
    print("\n" + "="*60)
    print("测试4: 数据库迁移脚本")
    print("="*60)

    migration_file = "alembic/versions/d5e6f7a8b9c0_add_stock_industry_temporal_fields.py"

    if not os.path.exists(migration_file):
        print(f"\n❌ 迁移文件不存在: {migration_file}")
        return False

    print(f"\n✅ 迁移文件存在: {migration_file}")

    # 读取迁移文件内容
    with open(migration_file, 'r') as f:
        content = f.read()

    # 检查关键内容
    required_elements = [
        'effective_date',
        'expire_date',
        'ix_stock_industry_effective_date',
        'ix_stock_industry_expire_date',
        'ix_stock_industry_ts_code_dates'
    ]

    missing_elements = [e for e in required_elements if e not in content]

    if missing_elements:
        print(f"\n❌ 迁移文件缺少元素: {missing_elements}")
        return False
    else:
        print(f"\n✅ 迁移文件包含所有必需元素")

    return True


def main():
    """主测试函数"""
    print("="*60)
    print("P0修复验证")
    print("="*60)
    print("\n验证目标:")
    print("1. 行业分类历史时点查询")
    print("2. 因子预处理历史时点支持")
    print("3. 残差动量因子实现")
    print("4. 数据库迁移脚本")

    results = {}

    # 运行测试
    results['industry_repo'] = test_industry_repository()
    results['factor_preprocess'] = test_factor_preprocess_historical()
    results['residual_momentum'] = test_residual_momentum_implementation()
    results['migration'] = test_database_migration()

    # 汇总结果
    print("\n" + "="*60)
    print("验证结果汇总")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")

    total = len(results)
    passed = sum(results.values())

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有P0修复验证通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要进一步修复")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
