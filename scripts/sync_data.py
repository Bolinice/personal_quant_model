#!/usr/bin/env python
"""
数据同步脚本
从 AKShare/Tushare 同步真实市场数据
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from app.services.data_sync_service import DataSyncService
from app.core.config import settings
from app.core.logging import logger


def main():
    """主函数"""
    print("=" * 60)
    print("  数据同步服务")
    print("=" * 60)

    # 配置
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')  # 同步一年数据

    print(f"\n同步时间范围: {start_date} ~ {end_date}")
    print(f"主数据源: {settings.PRIMARY_DATA_SOURCE}")

    # 创建同步服务
    service = DataSyncService(
        primary_source=settings.PRIMARY_DATA_SOURCE,
        tushare_token=settings.TUSHARE_TOKEN if settings.TUSHARE_TOKEN else None,
        tushare_proxy_url=settings.TUSHARE_PROXY_URL if settings.TUSHARE_PROXY_URL else None,
    )

    # 检查数据源连接
    available = service.get_available_source()
    if not available:
        print("\n错误: 没有可用的数据源连接")
        print("请检查网络连接或配置正确的 Tushare Token")
        return

    print(f"可用数据源: {available}")

    # 执行同步
    print("\n开始同步数据...")

    try:
        # 1. 同步交易日历
        print("\n[1/4] 同步交易日历...")
        count = service.sync_trading_calendar(start_date, end_date)
        print(f"      同步 {count} 条记录")

        # 2. 同步股票基础信息
        print("\n[2/4] 同步股票基础信息...")
        count = service.sync_stock_basic()
        print(f"      同步 {count} 条记录")

        # 3. 同步主要指数
        print("\n[3/4] 同步指数数据...")
        index_codes = ['000300.SH', '000905.SH', '000852.SH']
        total = 0
        for code in index_codes:
            count = service.sync_index_daily(code, start_date, end_date)
            total += count
            print(f"      {code}: {count} 条记录")
        print(f"      共计 {total} 条记录")

        # 4. 同步股票日线（可选，数据量大）
        print("\n[4/4] 同步股票日线数据...")
        print("      提示: 股票日线数据量较大，建议分批同步")
        print("      可使用 --sync-stocks 参数指定股票代码")

        # 默认只同步沪深300成分股
        from app.data_sources import get_data_source
        source = get_data_source(available)
        hs300_codes = source.get_index_components('000300.SH')

        if hs300_codes:
            print(f"      将同步沪深300成分股 ({len(hs300_codes)} 只)")
            count = service.sync_stock_daily_batch(hs300_codes, start_date, end_date)
            print(f"      同步 {count} 条记录")
        else:
            print("      无法获取沪深300成分股，跳过")

    except Exception as e:
        print(f"\n同步出错: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("  数据同步完成")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据同步脚本")
    parser.add_argument("--start-date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--sync-stocks", nargs='+', help="指定股票代码列表")

    args = parser.parse_args()

    main()
