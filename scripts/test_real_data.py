"""
测试真实数据接入
验证 AKShare 数据源是否正常工作
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from app.data_sources import AKShareDataSource, TushareDataSource

def test_akshare():
    """测试 AKShare 数据源"""
    print("=" * 60)
    print("测试 AKShare 数据源")
    print("=" * 60)

    source = AKShareDataSource()

    # 1. 连接测试
    print("\n[1] 连接测试...")
    connected = source.connect()
    print(f"    连接状态: {'成功' if connected else '失败'}")

    if not connected:
        print("    无法连接，跳过后续测试")
        return

    # 2. 获取股票日线数据
    print("\n[2] 获取股票日线数据 (600000.SH 浦发银行)...")
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    df = source.get_stock_daily('600000.SH', start_date, end_date)
    if not df.empty:
        print(f"    获取到 {len(df)} 条记录")
        print(f"    日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
        print(f"    最新收盘价: {df['close'].iloc[-1]:.2f}")
        print("\n    最近5天数据:")
        print(df[['trade_date', 'open', 'high', 'low', 'close', 'volume']].tail().to_string(index=False))
    else:
        print("    未获取到数据")

    # 3. 获取指数数据
    print("\n[3] 获取指数日线数据 (000300.SH 沪深300)...")
    df_index = source.get_index_daily('000300.SH', start_date, end_date)
    if not df_index.empty:
        print(f"    获取到 {len(df_index)} 条记录")
        print(f"    最新收盘: {df_index['close'].iloc[-1]:.2f}")
    else:
        print("    未获取到数据")

    # 4. 获取交易日历
    print("\n[4] 获取交易日历...")
    df_cal = source.get_trading_calendar(start_date, end_date)
    if not df_cal.empty:
        print(f"    获取到 {len(df_cal)} 个交易日")
    else:
        print("    未获取到数据")

    # 5. 获取股票列表
    print("\n[5] 获取股票基础信息...")
    df_basic = source.get_stock_basic()
    if not df_basic.empty:
        print(f"    获取到 {len(df_basic)} 只股票")
        print("\n    前10只股票:")
        print(df_basic[['ts_code', 'name', 'market']].head(10).to_string(index=False))
    else:
        print("    未获取到数据")

    # 6. 获取指数成分股
    print("\n[6] 获取沪深300成分股...")
    components = source.get_index_components('000300.SH')
    if components:
        print(f"    获取到 {len(components)} 只成分股")
        print(f"    前10只: {components[:10]}")
    else:
        print("    未获取到数据")

    print("\n" + "=" * 60)
    print("AKShare 测试完成")
    print("=" * 60)


def test_tushare(token: str = None):
    """测试 Tushare 数据源"""
    print("\n" + "=" * 60)
    print("测试 Tushare 数据源")
    print("=" * 60)

    if not token:
        print("\n    未提供 Tushare Token，跳过测试")
        print("    可在 https://tushare.pro 注册获取")
        return

    source = TushareDataSource(token=token)

    # 连接测试
    print("\n[1] 连接测试...")
    connected = source.connect()
    print(f"    连接状态: {'成功' if connected else '失败'}")

    if not connected:
        return

    # 获取日线数据
    print("\n[2] 获取股票日线数据...")
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    df = source.get_stock_daily('600000.SH', start_date, end_date)
    if not df.empty:
        print(f"    获取到 {len(df)} 条记录")
        print(df[['trade_date', 'close', 'pct_chg']].tail().to_string(index=False))
    else:
        print("    未获取到数据")


def test_data_sync():
    """测试数据同步服务"""
    print("\n" + "=" * 60)
    print("测试数据同步服务")
    print("=" * 60)

    from app.services.data_sync_service import DataSyncService

    service = DataSyncService(primary_source='akshare')

    # 同步交易日历
    print("\n[1] 同步交易日历 (最近3个月)...")
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    count = service.sync_trading_calendar(start_date, end_date)
    print(f"    同步了 {count} 条交易日历记录")

    # 同步股票基础信息
    print("\n[2] 同步股票基础信息...")
    count = service.sync_stock_basic()
    print(f"    同步了 {count} 条股票基础信息")

    # 同步单只股票日线
    print("\n[3] 同步股票日线数据 (600000.SH)...")
    count = service.sync_stock_daily('600000.SH', start_date, end_date)
    print(f"    同步了 {count} 条日线记录")

    # 同步指数数据
    print("\n[4] 同步沪深300指数...")
    count = service.sync_index_daily('000300.SH', start_date, end_date)
    print(f"    同步了 {count} 条指数记录")

    print("\n" + "=" * 60)
    print("数据同步测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试真实数据接入")
    parser.add_argument("--tushare-token", help="Tushare Token")
    parser.add_argument("--sync", action="store_true", help="测试数据同步服务")

    args = parser.parse_args()

    # 测试 AKShare
    test_akshare()

    # 测试 Tushare
    test_tushare(args.tushare_token)

    # 测试数据同步
    if args.sync:
        test_data_sync()
