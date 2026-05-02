#!/usr/bin/env python
"""
测试 Tushare 配置
验证 token 和代理 URL 是否正确配置
"""
import sys
sys.path.insert(0, '.')

from app.core.config import settings
from app.data_sources.tushare_source import TushareSource


def main():
    print("=" * 60)
    print("  Tushare 配置测试")
    print("=" * 60)

    # 显示配置
    print(f"\nTushare Token: {settings.TUSHARE_TOKEN[:20]}...{settings.TUSHARE_TOKEN[-10:]}" if settings.TUSHARE_TOKEN else "未配置")
    print(f"Tushare 代理 URL: {settings.TUSHARE_PROXY_URL}" if settings.TUSHARE_PROXY_URL else "未配置代理")
    print(f"Token 长度: {len(settings.TUSHARE_TOKEN)}" if settings.TUSHARE_TOKEN else "0")

    if not settings.TUSHARE_TOKEN:
        print("\n错误: TUSHARE_TOKEN 未配置")
        print("请在 .env 文件中设置 TUSHARE_TOKEN")
        return

    # 创建数据源
    print("\n初始化 TushareSource...")
    source = TushareSource(
        token=settings.TUSHARE_TOKEN,
        proxy_url=settings.TUSHARE_PROXY_URL if settings.TUSHARE_PROXY_URL else None
    )

    # 测试连接
    print("\n测试连接: 获取 2026-04-23 的日线数据...")
    try:
        df = source.get_stock_daily(trade_date="20260423")
        print(f"[成功] 获取到 {len(df)} 条记录")
        print(f"[成功] 列名: {list(df.columns)}")

        if len(df) > 0:
            print(f"\n前3条数据:")
            print(df.head(3).to_string())

        print("\n✅ Tushare 配置测试通过!")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
