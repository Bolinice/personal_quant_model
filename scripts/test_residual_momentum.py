#!/usr/bin/env python3
"""
测试残差动量因子计算
"""
import sys
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.base import SessionLocal
from app.models.market.stock_daily import StockDaily
from app.core.factors.momentum import calc_residual_momentum_factors
from sqlalchemy import select


def load_style_factors(end_date: date, lookback_days: int = 150) -> pd.DataFrame:
    """加载历史窗口的风格因子数据"""
    start_date = end_date - timedelta(days=lookback_days * 2)

    style_factors_dir = project_root / "data" / "style_factors"
    all_factors = []

    # 遍历所有可用的风格因子文件
    for parquet_file in sorted(style_factors_dir.glob("*.parquet")):
        file_date_str = parquet_file.stem
        try:
            file_date = date(int(file_date_str[:4]), int(file_date_str[4:6]), int(file_date_str[6:8]))

            if start_date <= file_date <= end_date:
                df = pd.read_parquet(parquet_file)
                df['trade_date'] = file_date
                all_factors.append(df)
        except (ValueError, IndexError):
            continue

    if not all_factors:
        print(f"❌ 未找到风格因子文件 ({start_date} 至 {end_date})")
        return pd.DataFrame()

    # 合并所有日期的数据
    combined = pd.concat(all_factors, ignore_index=True)

    # 转换为MultiIndex格式 (date, ts_code)
    combined = combined.set_index(['trade_date', 'ts_code'])

    print(f"✅ 加载风格因子: {len(all_factors)} 个交易日, {len(combined.columns)} 个因子")
    print(f"   日期范围: {combined.index.get_level_values(0).min()} 至 {combined.index.get_level_values(0).max()}")
    print(f"   因子列: {list(combined.columns)}")

    return combined


def load_returns(end_date: date, lookback_days: int = 150) -> pd.DataFrame:
    """加载股票收益率数据"""
    start_date = end_date - timedelta(days=lookback_days * 2)  # 预留足够的日历日

    session = SessionLocal()
    try:
        stmt = select(
            StockDaily.trade_date,
            StockDaily.ts_code,
            StockDaily.close,
            StockDaily.pct_chg
        ).where(
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).order_by(
            StockDaily.ts_code,
            StockDaily.trade_date
        )

        result = session.execute(stmt)
        rows = result.fetchall()

        if not rows:
            print(f"❌ 未找到收益率数据 ({start_date} 至 {end_date})")
            return pd.DataFrame()

        # 转换为DataFrame
        df = pd.DataFrame(rows, columns=['trade_date', 'ts_code', 'close', 'pct_chg'])

        # 转换Decimal类型为float
        df['close'] = df['close'].astype(float)
        df['pct_chg'] = df['pct_chg'].astype(float)

        # 计算日收益率 (如果pct_chg不可用)
        df['return'] = df.groupby('ts_code')['close'].pct_change()
        df['return'] = df['return'].fillna(df['pct_chg'] / 100.0)  # 回退到pct_chg

        # 透视为宽表格式: index=日期, columns=股票代码, values=收益率
        returns_wide = df.pivot(index='trade_date', columns='ts_code', values='return')

        print(f"✅ 加载收益率数据: {len(returns_wide)} 个交易日, {len(returns_wide.columns)} 只股票")
        print(f"   日期范围: {returns_wide.index.min()} 至 {returns_wide.index.max()}")

        return returns_wide

    finally:
        session.close()


def test_residual_momentum(test_date: date):
    """测试残差动量因子计算"""
    print(f"\n{'='*60}")
    print(f"测试残差动量因子计算 - {test_date}")
    print(f"{'='*60}\n")

    # 1. 加载风格因子
    print("步骤 1: 加载风格因子数据")
    style_factors = load_style_factors(test_date, lookback_days=150)
    if style_factors.empty:
        print("❌ 测试失败: 无法加载风格因子")
        return False

    # 2. 加载收益率数据
    print("\n步骤 2: 加载收益率数据")
    returns = load_returns(test_date, lookback_days=150)
    if returns.empty:
        print("❌ 测试失败: 无法加载收益率数据")
        return False

    # 3. 计算残差动量因子
    print("\n步骤 3: 计算残差动量因子")
    try:
        residual_factors = calc_residual_momentum_factors(
            returns=returns,
            style_factors=style_factors,
            windows=[20, 60, 120]
        )

        if residual_factors.empty:
            print("❌ 测试失败: 残差动量因子计算结果为空")
            return False

        print(f"✅ 残差动量因子计算成功")
        print(f"   结果形状: {residual_factors.shape}")
        print(f"   因子列: {list(residual_factors.columns)}")

        # 4. 检查结果质量
        print("\n步骤 4: 检查结果质量")
        for col in residual_factors.columns:
            valid_count = residual_factors[col].notna().sum()
            valid_pct = valid_count / len(residual_factors) * 100
            mean_val = residual_factors[col].mean()
            std_val = residual_factors[col].std()

            print(f"   {col}:")
            print(f"     - 有效值: {valid_count}/{len(residual_factors)} ({valid_pct:.1f}%)")
            print(f"     - 均值: {mean_val:.6f}")
            print(f"     - 标准差: {std_val:.6f}")

        # 5. 显示样本数据
        print("\n步骤 5: 样本数据（最后5个交易日）")
        print(residual_factors.tail())

        print("\n✅ 测试通过!")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    # 测试日期：使用最近有风格因子数据的日期
    test_date = date(2026, 4, 17)

    success = test_residual_momentum(test_date)

    if success:
        print("\n" + "="*60)
        print("🎉 残差动量因子测试全部通过!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("❌ 残差动量因子测试失败")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()
