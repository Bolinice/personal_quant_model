"""
全量数据补充脚本 — 补充因子计算所需的所有缺失数据
按依赖顺序执行:
  1. 原始财务报表 (income + balancesheet + cashflow + TTM + prev)
  2. 资金流向完整字段 (大单/超大单净流入)
  3. 北向持股数据 (north_holding, north_holding_pct)
  4. 日线大单成交量 (large_order_volume, super_large_order_volume, turnover_rate)
  5. 行业级别数据 (行业动量/资金流/估值)
  6. 股权质押/前十大股东/机构持仓/分析师一致预期

用法:
  python scripts/sync_all_factor_data.py              # 全量补充
  python scripts/sync_all_factor_data.py --skip financial  # 跳过财务数据
  python scripts/samp_all_factor_data.py --only industry   # 只同步行业数据
"""

import sys
import time
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def run_step(name: str, cmd: str) -> bool:
    """运行同步步骤"""
    import subprocess
    logger.info(f"===== 开始: {name} =====")
    try:
        result = subprocess.run(
            cmd, shell=True, timeout=3600,
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            logger.info(f"===== 完成: {name} =====")
            return True
        else:
            logger.error(f"===== 失败: {name} =====\n{result.stderr[-500:]}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"===== 超时: {name} =====")
        return False
    except Exception as e:
        logger.error(f"===== 异常: {name} =====\n{e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='全量数据补充')
    parser.add_argument('--skip', nargs='*', default=[], help='跳过的步骤')
    parser.add_argument('--only', type=str, default=None, help='只运行指定步骤')
    args = parser.parse_args()

    steps = [
        ('financial', '原始财务报表 (income+balancesheet+cashflow+TTM)',
         'python scripts/sync_financial_raw.py'),
        ('money_flow', '资金流向完整字段',
         'python scripts/sync_money_flow.py --source tushare --days 30'),
        ('northbound', '北向持股数据',
         'python scripts/sync_northbound.py'),
        ('order_volume', '日线大单成交量+换手率',
         'python scripts/sync_daily_order_volume.py --days 30'),
        ('industry', '行业级别数据',
         'python scripts/sync_industry_daily.py'),
        ('pledge', '股权质押数据',
         'python scripts/sync_shareholder_pledge.py'),
        ('top10', '前十大股东数据',
         'python scripts/sync_top10_holders.py'),
        ('institutional', '机构持仓数据',
         'python scripts/sync_institutional_holding.py'),
        ('analyst', '分析师一致预期',
         'python scripts/sync_analyst_consensus.py'),
        ('status', '股票状态日表',
         'python scripts/sync_status_daily.py'),
    ]

    if args.only:
        steps = [(n, d, c) for n, d, c in steps if n == args.only]

    results = {}
    t0 = time.time()

    for name, desc, cmd in steps:
        if name in args.skip:
            logger.info(f"跳过: {desc}")
            results[name] = 'skipped'
            continue

        ok = run_step(desc, cmd)
        results[name] = 'ok' if ok else 'failed'

    elapsed = time.time() - t0
    logger.info(f"\n{'='*60}")
    logger.info(f"数据补充完成! 耗时 {elapsed/60:.1f}min")
    for name, status in results.items():
        logger.info(f"  {name}: {status}")
    logger.info(f"{'='*60}")


if __name__ == '__main__':
    main()
