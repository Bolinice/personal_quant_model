"""
数据质量校验服务
- 缺失交易日检查
- 价格异常检查
- 成交量零值检查
- 财务数据勾稽关系检查
"""

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def check_missing_trading_days(
    db: Session,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """检查缺失的交易日

    对比交易日历与实际数据，找出缺失的交易日。
    """
    # 获取交易日历中应开市的日期
    calendar_days = db.execute(
        text(
            "SELECT cal_date FROM trading_calendar "
            "WHERE is_open = 1 AND cal_date BETWEEN :start AND :end "
            "ORDER BY cal_date"
        ),
        {"start": start_date, "end": end_date},
    ).fetchall()

    # 获取实际有数据的日期
    data_days = db.execute(
        text(
            "SELECT DISTINCT trade_date FROM stock_daily WHERE trade_date BETWEEN :start AND :end ORDER BY trade_date"
        ),
        {"start": start_date, "end": end_date},
    ).fetchall()

    calendar_set = {row[0] for row in calendar_days}
    data_set = {row[0] for row in data_days}
    missing = sorted(calendar_set - data_set)

    return {
        "check": "missing_trading_days",
        "total_calendar_days": len(calendar_set),
        "total_data_days": len(data_set),
        "missing_count": len(missing),
        "missing_dates": [str(d) for d in missing[:20]],  # 最多返回20个
        "status": "pass" if len(missing) == 0 else "warning",
    }


def check_price_anomaly(
    db: Session,
    trade_date: date | None = None,
    threshold: float = 0.20,
) -> dict[str, Any]:
    """检查价格异常（日涨跌幅超过阈值）

    Args:
        threshold: 涨跌幅阈值，默认20%
    """
    if trade_date is None:
        trade_date = date.today() - timedelta(days=1)

    anomalies = db.execute(
        text(
            "SELECT ts_code, trade_date, pct_chg "
            "FROM stock_daily "
            "WHERE trade_date = :date AND ABS(pct_chg) > :threshold "
            "ORDER BY ABS(pct_chg) DESC LIMIT 50"
        ),
        {"date": trade_date, "threshold": threshold * 100},
    ).fetchall()

    return {
        "check": "price_anomaly",
        "trade_date": str(trade_date),
        "threshold": f"{threshold * 100}%",
        "anomaly_count": len(anomalies),
        "anomalies": [{"ts_code": row[0], "trade_date": str(row[1]), "pct_chg": row[2]} for row in anomalies[:20]],
        "status": "pass" if len(anomalies) == 0 else "warning",
    }


def check_zero_volume(
    db: Session,
    trade_date: date | None = None,
) -> dict[str, Any]:
    """检查成交量为零但价格非零的异常"""
    if trade_date is None:
        trade_date = date.today() - timedelta(days=1)

    zero_vol = db.execute(
        text(
            "SELECT ts_code, trade_date, close "
            "FROM stock_daily "
            "WHERE trade_date = :date AND vol = 0 AND close > 0 "
            "LIMIT 50"
        ),
        {"date": trade_date},
    ).fetchall()

    return {
        "check": "zero_volume_with_price",
        "trade_date": str(trade_date),
        "count": len(zero_vol),
        "records": [{"ts_code": row[0], "trade_date": str(row[1]), "close": float(row[2])} for row in zero_vol[:20]],
        "status": "pass" if len(zero_vol) == 0 else "warning",
    }


def check_financial_consistency(
    db: Session,
    report_date: date | None = None,
) -> dict[str, Any]:
    """检查财务数据勾稽关系

    基本勾稽: 总资产 = 总负债 + 净资产
    """
    if report_date is None:
        report_date = date.today() - timedelta(days=90)

    # 简化检查：查找总资产与负债+净资产偏差超过1%的记录
    inconsistent = db.execute(
        text(
            "SELECT ts_code, ann_date, "
            "total_assets, total_liab, total_hldr_eqy_exc_min_int, "
            "ABS(total_assets - total_liab - total_hldr_eqy_exc_min_int) / NULLIF(total_assets, 0) as deviation "
            "FROM stock_financial "
            "WHERE ann_date >= :date "
            "AND total_assets IS NOT NULL AND total_assets != 0 "
            "AND ABS(total_assets - total_liab - total_hldr_eqy_exc_min_int) / ABS(total_assets) > 0.01 "
            "LIMIT 50"
        ),
        {"date": report_date},
    ).fetchall()

    return {
        "check": "financial_consistency",
        "report_date": str(report_date),
        "inconsistent_count": len(inconsistent),
        "records": [
            {
                "ts_code": row[0],
                "ann_date": str(row[1]),
                "deviation": f"{float(row[5]) * 100:.2f}%",
            }
            for row in inconsistent[:20]
        ],
        "status": "pass" if len(inconsistent) == 0 else "warning",
    }


def run_all_checks(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """运行所有数据质量检查"""
    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    results = []
    checks = [
        lambda: check_missing_trading_days(db, start_date, end_date),
        lambda: check_price_anomaly(db, end_date),
        lambda: check_zero_volume(db, end_date),
        lambda: check_financial_consistency(db),
    ]

    for check_fn in checks:
        try:
            result = check_fn()
            results.append(result)
        except Exception as e:
            logger.warning(f"数据质量检查失败: {e}")
            results.append({"check": "unknown", "status": "error", "error": str(e)})

    all_pass = all(r.get("status") == "pass" for r in results)

    return {
        "overall_status": "pass" if all_pass else "warning",
        "checks": results,
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r.get("status") == "pass"),
            "warning": sum(1 for r in results if r.get("status") == "warning"),
            "error": sum(1 for r in results if r.get("status") == "error"),
        },
    }
