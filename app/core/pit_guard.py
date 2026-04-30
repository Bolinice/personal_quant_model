"""
PIT Guard - 点在时数据守卫
========================
在数据访问层强制 ann_date <= trade_date，从架构层面杜绝未来函数。

核心原则：
- 所有财务数据必须按公告发布日期使用，禁止使用尚未公告的数据
- 同一报告期有多条记录时，取 ann_date <= trade_date 中最新的一条
- 任何绕过 PIT Guard 的财务数据查询都应被视为潜在的前瞻偏差源
"""

import logging
import warnings
from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy.orm import Query, Session

logger = logging.getLogger(__name__)


def pit_filter_df(
    financial_df: pd.DataFrame,
    trade_date: date | str,
    ann_date_col: str = "ann_date",
    code_col: str = "ts_code",
    period_col: str | None = None,
) -> pd.DataFrame:
    """
    PIT 过滤 DataFrame：仅保留 ann_date <= trade_date 的财务数据。

    对于同一股票同一报告期有多条记录的情况，取 ann_date <= trade_date 中最新的一条。

    Args:
        financial_df: 财务数据 DataFrame，需包含 ann_date 列
        trade_date: 当前交易日期
        ann_date_col: 公告日期列名
        code_col: 股票代码列名
        period_col: 报告期列名，用于去重（自动检测 end_date / report_period）

    Returns:
        过滤后的 DataFrame
    """
    if financial_df.empty:
        return financial_df

    if ann_date_col not in financial_df.columns:
        warnings.warn(
            f"Financial data missing '{ann_date_col}' column, "
            "PIT filtering cannot be applied. This may introduce look-ahead bias.",
            UserWarning,
            stacklevel=2,
        )
        return financial_df

    # 统一日期类型
    ann_dates = pd.to_datetime(financial_df[ann_date_col])
    trade_dt = pd.to_datetime(trade_date)

    # 核心约束：仅保留公告日 <= 交易日的记录
    mask = ann_dates <= trade_dt
    filtered = financial_df.loc[mask].copy()

    leaked_count = mask.sum() - len(financial_df) if not mask.all() else 0
    if leaked_count > 0:
        logger.warning("PIT guard filtered %d future rows (ann_date > %s)", leaked_count, trade_date)

    if filtered.empty:
        return filtered

    # 同一股票同一报告期，取最新公告记录
    if period_col and period_col in filtered.columns:
        dedup_col = period_col
    elif "report_period" in filtered.columns:
        dedup_col = "report_period"
    elif "end_date" in filtered.columns:
        dedup_col = "end_date"
    else:
        return filtered

    filtered = filtered.sort_values([ann_date_col], ascending=False)
    return filtered.drop_duplicates(subset=[code_col, dedup_col], keep="first")


def pit_filter_query(
    query,
    model_class,
    trade_date: date | str,
    session: Session,
    ann_date_col: str = "ann_date",
) -> Query:
    """
    PIT 过滤 SQLAlchemy Query：添加 ann_date <= trade_date 条件。

    用法:
        query = db.query(StockFinancial).filter(StockFinancial.ts_code.in_(ts_codes))
        query = pit_filter_query(query, StockFinancial, trade_date, db)
        results = query.all()

    Args:
        query: SQLAlchemy Query 对象
        model_class: ORM 模型类（需有 ann_date 属性）
        trade_date: 当前交易日期
        session: 数据库 session
        ann_date_col: 公告日期列名

    Returns:
        添加了 PIT 过滤条件的 Query
    """
    ann_col = getattr(model_class, ann_date_col, None)
    if ann_col is None:
        logger.warning(
            "Model %s has no '%s' column, PIT filtering skipped. This may introduce look-ahead bias.",
            model_class.__name__,
            ann_date_col,
        )
        return query

    # 统一转换为 date 对象
    if isinstance(trade_date, str):
        trade_date = (
            datetime.strptime(trade_date, "%Y%m%d").replace(tzinfo=UTC).date()
            if len(trade_date) == 8
            else datetime.strptime(trade_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
        )
    return query.filter(ann_col <= trade_date)


class PITGuardMixin:
    """
    PIT Guard Mixin - 可混入 Service 类，自动为财务数据查询添加 PIT 过滤。

    用法:
        class MarketService(PITGuardMixin):
            def get_financial_data(self, ts_code, trade_date, db):
                query = db.query(StockFinancial).filter(StockFinancial.ts_code == ts_code)
                query = self.pit_filter(query, StockFinancial, trade_date, db)
                return query.all()
    """

    @staticmethod
    def pit_filter(query, model_class, trade_date, session, ann_date_col="ann_date"):
        """为查询添加 PIT 过滤条件"""
        return pit_filter_query(query, model_class, trade_date, session, ann_date_col)

    @staticmethod
    def pit_filter_df(df: pd.DataFrame, trade_date, ann_date_col="ann_date", **kwargs) -> pd.DataFrame:
        """为 DataFrame 添加 PIT 过滤"""
        return pit_filter_df(df, trade_date, ann_date_col=ann_date_col, **kwargs)
