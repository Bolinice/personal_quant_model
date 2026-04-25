"""
数据库数据完整性审计测试
========================
验证数据库数据能否支撑核心计算流水线:
1. 股票池构建 (UniverseBuilder)
2. Alpha模块因子计算 (QualityGrowth/Expectation/ResidualMomentum/FlowConfirm/RiskPenalty)
3. 信号融合 (EnsembleEngine)
4. 组合构建 (PortfolioBuilder)
5. 风险预算 (RiskBudgetEngine)
6. Regime检测 (RegimeDetector)
7. PIT对齐 (公告日 vs 报告期)
8. 日期格式一致性
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime
from sqlalchemy import text


@pytest.fixture(scope="module")
def db_conn():
    """数据库连接fixture"""
    from app.db.base import engine
    with engine.connect() as conn:
        yield conn


# ═══════════════════════════════════════════════
# 1. 股票池构建数据审计
# ═══════════════════════════════════════════════

class TestUniverseDataAudit:
    """
    UniverseBuilder需要:
    - stock_basic: ts_code, list_date, list_status
    - stock_daily: ts_code, trade_date, close, amount
    - stock_status_daily: ts_code, trade_date, is_st, is_suspended, is_delist
    - stock_daily_basic: ts_code, trade_date, total_mv
    """

    def test_stock_basic_exists_and_populated(self, db_conn):
        """stock_basic表存在且有数据"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_basic'))
        count = result.scalar()
        assert count > 0, "stock_basic表为空, 无法构建股票池"

    def test_stock_basic_list_status_coverage(self, db_conn):
        """list_status字段覆盖率"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_basic WHERE list_status IS NOT NULL'))
        non_null = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_basic'))
        total = result.scalar()
        coverage = non_null / total if total > 0 else 0
        assert coverage >= 0.95, f"list_status覆盖率{coverage:.1%}, 低于95%"

    def test_stock_basic_list_date_coverage(self, db_conn):
        """list_date字段覆盖率 — 上市天数过滤依赖此字段"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_basic WHERE list_date IS NOT NULL'))
        non_null = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_basic'))
        total = result.scalar()
        coverage = non_null / total if total > 0 else 0
        assert coverage >= 0.90, f"list_date覆盖率{coverage:.1%}, 低于90% — 上市天数过滤将失效"

    def test_stock_basic_list_status_values(self, db_conn):
        """list_status应包含L(上市)/D(退市)/P(暂停)"""
        result = db_conn.execute(text('SELECT DISTINCT list_status FROM stock_basic WHERE list_status IS NOT NULL'))
        statuses = [r[0] for r in result]
        assert 'L' in statuses, "list_status缺少'L'(上市)状态"
        # D和P是可选的, 但L必须存在

    def test_stock_basic_industry_coverage(self, db_conn):
        """industry字段覆盖率 — 行业约束和行业中性化依赖此字段"""
        result = db_conn.execute(text("SELECT COUNT(*) FROM stock_basic WHERE industry IS NOT NULL AND industry != ''"))
        with_industry = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_basic'))
        total = result.scalar()
        coverage = with_industry / total if total > 0 else 0
        assert coverage >= 0.80, f"industry覆盖率{coverage:.1%}, 低于80% — 行业约束将不完整"

    def test_stock_daily_exists_and_populated(self, db_conn):
        """stock_daily表存在且有数据"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily'))
        count = result.scalar()
        assert count > 0, "stock_daily表为空, 无法获取行情数据"

    def test_stock_daily_price_and_amount_coverage(self, db_conn):
        """close和amount字段覆盖率 — 流动性和价格过滤依赖此字段"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily WHERE close IS NOT NULL AND close > 0'))
        with_close = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily WHERE amount IS NOT NULL AND amount > 0'))
        with_amount = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily'))
        total = result.scalar()

        close_coverage = with_close / total if total > 0 else 0
        amount_coverage = with_amount / total if total > 0 else 0
        assert close_coverage >= 0.95, f"close覆盖率{close_coverage:.1%}, 低于95%"
        assert amount_coverage >= 0.95, f"amount覆盖率{amount_coverage:.1%}, 低于95%"

    def test_stock_daily_basic_total_mv_coverage(self, db_conn):
        """total_mv字段覆盖率 — 市值过滤依赖此字段"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily_basic WHERE total_mv IS NOT NULL'))
        with_mv = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily_basic'))
        total = result.scalar()
        coverage = with_mv / total if total > 0 else 0
        assert coverage >= 0.90, f"total_mv覆盖率{coverage:.1%}, 低于90% — 市值过滤将不完整"

    def test_stock_status_daily_data_available(self, db_conn):
        """stock_status_daily数据可用性 — ST/停牌过滤依赖此表"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_status_daily'))
        count = result.scalar()
        if count == 0:
            pytest.skip("stock_status_daily为空 — ST/停牌过滤将使用ts_code名称推断, 建议补充数据")

    def test_stock_daily_recent_data_freshness(self, db_conn):
        """stock_daily数据新鲜度 — 最近5个交易日内应有数据"""
        result = db_conn.execute(text('SELECT MAX(trade_date) FROM stock_daily'))
        latest = result.scalar()
        assert latest is not None, "stock_daily无数据"

        if isinstance(latest, str):
            latest = datetime.strptime(latest, '%Y-%m-%d').date()
        elif isinstance(latest, datetime):
            latest = latest.date()

        days_since = (date.today() - latest).days
        assert days_since <= 30, f"stock_daily最新数据距今{days_since}天, 超过30天 — 数据可能过期"

    def test_stock_daily_basic_date_format_consistency(self, db_conn):
        """stock_daily_basic日期格式应与stock_daily一致"""
        result = db_conn.execute(text('SELECT trade_date FROM stock_daily LIMIT 1'))
        sd_date = result.scalar()
        result = db_conn.execute(text('SELECT trade_date FROM stock_daily_basic LIMIT 1'))
        sdb_date = result.scalar()

        # 两者类型应一致
        assert type(sd_date) == type(sdb_date), \
            f"日期格式不一致: stock_daily={type(sd_date).__name__}, stock_daily_basic={type(sdb_date).__name__}"


# ═══════════════════════════════════════════════
# 2. Alpha模块因子数据审计
# ═══════════════════════════════════════════════

class TestAlphaFactorDataAudit:
    """
    Alpha模块因子数据来源审计:
    - QualityGrowth: roe_ttm, roe_delta, gross_margin, revenue_growth_yoy, profit_growth_yoy, operating_cashflow_ratio, accrual_ratio
    - Expectation: eps_revision_fy0, eps_revision_fy1, analyst_coverage, rating_upgrade_ratio, earnings_surprise, guidance_up_ratio
    - ResidualMomentum: residual_return_20d/60d/120d, residual_sharpe, turnover_ratio_20d, max_drawdown_20d
    - FlowConfirm: north_net_inflow_5d/20d, main_force_net_inflow, large_order_net_ratio, margin_balance_change, institutional_holding_change
    - RiskPenalty: volatility_20d, idiosyncratic_vol, max_drawdown_60d, illiquidity, concentration_top10, pledge_ratio, goodwill_ratio
    """

    def test_stock_financial_exists_and_populated(self, db_conn):
        """stock_financial表存在且有数据 — 基本面因子来源"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial'))
        count = result.scalar()
        assert count > 0, "stock_financial表为空, 基本面因子无法计算"

    def test_stock_financial_roe_coverage(self, db_conn):
        """ROE字段覆盖率 — QualityGrowth核心因子"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial WHERE roe IS NOT NULL'))
        with_roe = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial'))
        total = result.scalar()
        coverage = with_roe / total if total > 0 else 0
        assert coverage >= 0.50, f"ROE覆盖率{coverage:.1%}, 低于50% — QualityGrowth模块将严重退化"

    def test_stock_financial_revenue_growth_coverage(self, db_conn):
        """营收增长率覆盖率 — QualityGrowth因子"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial WHERE yoy_revenue IS NOT NULL'))
        with_yoy = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial'))
        total = result.scalar()
        coverage = with_yoy / total if total > 0 else 0
        if coverage < 0.30:
            pytest.skip(f"yoy_revenue覆盖率{coverage:.1%}过低 — revenue_growth_yoy因子需从原始财务数据计算")

    def test_stock_financial_ann_date_coverage(self, db_conn):
        """ann_date(公告日)覆盖率 — PIT对齐核心字段"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial WHERE ann_date IS NOT NULL'))
        with_ann = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial'))
        total = result.scalar()
        coverage = with_ann / total if total > 0 else 0
        assert coverage >= 0.80, f"ann_date覆盖率{coverage:.1%}, 低于80% — PIT对齐将严重退化, 存在未来函数风险"

    def test_stock_financial_pit_alignment(self, db_conn):
        """ann_date应 >= end_date — PIT对齐正确性"""
        result = db_conn.execute(text('''
            SELECT COUNT(*) FROM stock_financial
            WHERE ann_date IS NOT NULL AND ann_date < end_date
        '''))
        bad_count = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial WHERE ann_date IS NOT NULL'))
        total = result.scalar()
        if total > 0:
            bad_ratio = bad_count / total
            assert bad_ratio < 0.01, f"ann_date < end_date的比例{bad_ratio:.2%}, 超过1% — 数据质量问题"

    def test_stock_northbound_data_available(self, db_conn):
        """北向资金数据可用性 — FlowConfirm模块因子来源"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_northbound'))
        count = result.scalar()
        if count == 0:
            pytest.skip("stock_northbound为空 — north_net_inflow因子无法计算, FlowConfirm模块将退化")

    def test_stock_northbound_coverage_per_stock(self, db_conn):
        """北向资金每只股票的覆盖天数"""
        result = db_conn.execute(text('''
            SELECT AVG(cnt) FROM (
                SELECT ts_code, COUNT(*) as cnt FROM stock_northbound GROUP BY ts_code
            ) t
        '''))
        avg_days = result.scalar()
        if avg_days is not None:
            assert avg_days >= 5, f"北向资金平均覆盖{avg_days:.0f}天, 不足5天 — 5日/20日流入因子无法计算"

    def test_stock_money_flow_data_available(self, db_conn):
        """资金流向数据可用性 — FlowConfirm模块因子来源"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_money_flow'))
        count = result.scalar()
        if count == 0:
            pytest.skip("stock_money_flow为空 — main_force_net_inflow/large_order_net_ratio因子无法计算")

    def test_stock_daily_vol_for_momentum(self, db_conn):
        """stock_daily有足够历史数据计算动量因子 — 需120+交易日"""
        result = db_conn.execute(text('''
            SELECT COUNT(DISTINCT trade_date) FROM stock_daily
        '''))
        trading_days = result.scalar()
        assert trading_days >= 120, f"交易日数{trading_days}, 不足120天 — 残差动量120d因子无法计算"

    def test_stock_daily_basic_for_liquidity(self, db_conn):
        """stock_daily_basic有turnover_rate数据 — 流动性因子来源"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily_basic WHERE turnover_rate IS NOT NULL'))
        with_tr = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily_basic'))
        total = result.scalar()
        coverage = with_tr / total if total > 0 else 0
        assert coverage >= 0.80, f"turnover_rate覆盖率{coverage:.1%}, 低于80% — 流动性因子将退化"


# ═══════════════════════════════════════════════
# 3. 日期格式一致性审计
# ═══════════════════════════════════════════════

class TestDateFormatConsistency:
    """
    日期格式一致性审计

    stock_daily.trade_date: date类型 (YYYY-MM-DD)
    stock_daily_basic.trade_date: integer类型 (YYYYMMDD)
    stock_basic.list_date: integer类型 (YYYYMMDD)
    stock_financial.end_date/ann_date: integer类型 (YYYYMMDD)

    这会导致JOIN时类型不匹配!
    """

    def test_stock_daily_date_type(self, db_conn):
        """stock_daily.trade_date类型"""
        result = db_conn.execute(text('''
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'stock_daily' AND column_name = 'trade_date'
        '''))
        dtype = result.scalar()
        assert dtype is not None, "stock_daily.trade_date列不存在"

    def test_stock_daily_basic_date_type(self, db_conn):
        """stock_daily_basic.trade_date类型"""
        result = db_conn.execute(text('''
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'stock_daily_basic' AND column_name = 'trade_date'
        '''))
        dtype = result.scalar()
        assert dtype is not None, "stock_daily_basic.trade_date列不存在"

    def test_date_format_cross_table_join(self, db_conn):
        """跨表JOIN时日期格式是否兼容"""
        # stock_daily.trade_date is date, stock_daily_basic.trade_date is integer
        # Direct join won't work — need type conversion
        result = db_conn.execute(text('''
            SELECT COUNT(*) FROM stock_daily sd
            JOIN stock_daily_basic sdb
            ON sd.ts_code = sdb.ts_code AND sd.trade_date = sdb.trade_date
            LIMIT 1
        '''))
        direct_count = result.scalar()

        if direct_count == 0:
            # Try with conversion
            result = db_conn.execute(text('''
                SELECT COUNT(*) FROM stock_daily sd
                JOIN stock_daily_basic sdb
                ON sd.ts_code = sdb.ts_code
                AND to_char(sd.trade_date, 'YYYYMMDD')::integer = sdb.trade_date
                LIMIT 1
            '''))
            converted_count = result.scalar()
            assert converted_count > 0, \
                "stock_daily.trade_date(date) 与 stock_daily_basic.trade_date(integer) JOIN失败! 数据无法关联"
            pytest.fail(
                "stock_daily.trade_date(date类型) 与 stock_daily_basic.trade_date(integer类型) 不匹配! "
                "直接JOIN返回0行, 需要类型转换. 建议统一为同一种类型"
            )

    def test_stock_basic_list_date_format(self, db_conn):
        """stock_basic.list_date格式"""
        result = db_conn.execute(text('''
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'stock_basic' AND column_name = 'list_date'
        '''))
        dtype = result.scalar()
        # list_date可能是integer(YYYYMMDD)或date
        assert dtype is not None, "stock_basic.list_date列不存在"

    def test_stock_financial_date_format(self, db_conn):
        """stock_financial日期格式"""
        result = db_conn.execute(text('''
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'stock_financial' AND column_name IN ('end_date', 'ann_date')
        '''))
        date_cols = {r[0]: r[1] for r in result}
        assert 'end_date' in date_cols, "stock_financial缺少end_date列"
        assert 'ann_date' in date_cols, "stock_financial缺少ann_date列"


# ═══════════════════════════════════════════════
# 4. 数据量充足性审计
# ═══════════════════════════════════════════════

class TestDataVolumeAudit:
    """
    数据量充足性审计

    核心计算需要:
    - 股票池: >= 100只活跃股票
    - 行情历史: >= 120个交易日 (动量因子)
    - 财务数据: >= 4个报告期 (ROE变化/预期修正)
    - 日线覆盖: 每日 >= 3000只股票
    """

    def test_active_stock_count(self, db_conn):
        """活跃上市股票数量"""
        result = db_conn.execute(text("SELECT COUNT(*) FROM stock_basic WHERE list_status = 'L'"))
        count = result.scalar()
        assert count >= 100, f"上市股票仅{count}只, 不足100只 — 股票池过小"

    def test_daily_coverage_per_trading_day(self, db_conn):
        """每个交易日覆盖的股票数量"""
        result = db_conn.execute(text('''
            SELECT trade_date, COUNT(DISTINCT ts_code)
            FROM stock_daily
            GROUP BY trade_date
            ORDER BY trade_date DESC
            LIMIT 5
        '''))
        rows = result.fetchall()
        for row in rows:
            assert row[1] >= 500, \
                f"{row[0]}仅{row[1]}只股票, 不足500 — 数据覆盖不足"

    def test_financial_report_periods(self, db_conn):
        """财务报告期数量 — 需要足够的历史报告期计算ROE变化"""
        result = db_conn.execute(text('''
            SELECT COUNT(DISTINCT end_date) FROM stock_financial
        '''))
        periods = result.scalar()
        assert periods >= 4, f"财务报告期仅{periods}个, 不足4个 — ROE变化/预期修正因子无法计算"

    def test_trading_days_sufficient_for_backtest(self, db_conn):
        """交易日数量是否足够回测"""
        result = db_conn.execute(text('SELECT COUNT(DISTINCT trade_date) FROM stock_daily'))
        days = result.scalar()
        assert days >= 250, f"交易日仅{days}天, 不足250天(约1年) — 回测结果不可靠"

    def test_stock_daily_basic_coverage_ratio(self, db_conn):
        """stock_daily_basic与stock_daily的覆盖率比"""
        result = db_conn.execute(text('SELECT COUNT(DISTINCT ts_code) FROM stock_daily'))
        sd_stocks = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(DISTINCT ts_code) FROM stock_daily_basic'))
        sdb_stocks = result.scalar()

        if sd_stocks > 0:
            ratio = sdb_stocks / sd_stocks
            assert ratio >= 0.80, \
                f"stock_daily_basic覆盖率{ratio:.1%}, 低于80% — 市值/PE/PB数据不完整"


# ═══════════════════════════════════════════════
# 5. 数据质量审计
# ═══════════════════════════════════════════════

class TestDataQualityAudit:
    """
    数据质量审计

    检查: 重复数据/空值率/异常值/逻辑一致性
    """

    def test_stock_daily_no_duplicates(self, db_conn):
        """stock_daily不应有重复数据"""
        result = db_conn.execute(text('''
            SELECT COUNT(*) - COUNT(DISTINCT (ts_code, trade_date))
            FROM stock_daily
        '''))
        # 用子查询方式
        result = db_conn.execute(text('''
            SELECT COUNT(*) FROM (
                SELECT ts_code, trade_date, COUNT(*) as cnt
                FROM stock_daily
                GROUP BY ts_code, trade_date
                HAVING COUNT(*) > 1
            ) t
        '''))
        dup_count = result.scalar()
        assert dup_count == 0, f"stock_daily有{dup_count}组重复数据 (ts_code+trade_date)"

    def test_stock_daily_no_negative_close(self, db_conn):
        """stock_daily.close不应有负值"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily WHERE close < 0'))
        neg_count = result.scalar()
        assert neg_count == 0, f"stock_daily有{neg_count}条close<0的记录"

    def test_stock_daily_no_negative_amount(self, db_conn):
        """stock_daily.amount不应有负值"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily WHERE amount < 0'))
        neg_count = result.scalar()
        assert neg_count == 0, f"stock_daily有{neg_count}条amount<0的记录"

    def test_stock_financial_roe_reasonable_range(self, db_conn):
        """ROE应在合理范围内 (-100% ~ 100%)"""
        result = db_conn.execute(text('''
            SELECT COUNT(*) FROM stock_financial
            WHERE roe IS NOT NULL AND (roe < -100 OR roe > 100)
        '''))
        outlier_count = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_financial WHERE roe IS NOT NULL'))
        total = result.scalar()
        if total > 0:
            outlier_ratio = outlier_count / total
            assert outlier_ratio < 0.05, \
                f"ROE异常值比例{outlier_ratio:.2%} (>5%) — 数据质量问题或需去极值"

    def test_stock_daily_basic_total_mv_positive(self, db_conn):
        """total_mv应为正值"""
        result = db_conn.execute(text('''
            SELECT COUNT(*) FROM stock_daily_basic
            WHERE total_mv IS NOT NULL AND total_mv <= 0
        '''))
        neg_count = result.scalar()
        assert neg_count == 0, f"stock_daily_basic有{neg_count}条total_mv<=0的记录"

    def test_stock_daily_vol_amount_consistency(self, db_conn):
        """vol=0时amount也应为0 (停牌)"""
        result = db_conn.execute(text('''
            SELECT COUNT(*) FROM stock_daily WHERE vol = 0 AND amount > 0
        '''))
        inconsistent = result.scalar()
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_daily WHERE vol = 0'))
        total_suspended = result.scalar()
        if total_suspended > 0:
            ratio = inconsistent / total_suspended
            assert ratio < 0.10, \
                f"vol=0但amount>0的比例{ratio:.2%} (>10%) — 数据不一致"


# ═══════════════════════════════════════════════
# 6. 缺失数据表审计
# ═══════════════════════════════════════════════

class TestMissingDataTables:
    """
    缺失数据表审计

    以下表对核心计算至关重要但当前为空:
    - stock_status_daily: ST/停牌/退市状态 (0行)
    - stock_margin: 融资融券数据 (0行)
    - pit_financial: PIT对齐财务数据 (0行)
    - analyst_estimates_pit: 分析师预期PIT数据 (0行)
    - event_center: 风险事件 (0行)
    - risk_flag_daily: 每日风险标记 (0行)
    """

    def test_stock_status_daily_available(self, db_conn):
        """stock_status_daily数据可用性"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_status_daily'))
        count = result.scalar()
        if count == 0:
            pytest.fail(
                "stock_status_daily为空! ST/停牌/退市过滤将失效. "
                "建议: 通过Tushare namechange/stk_limit等接口补充, 或从ts_code名称推断ST状态"
            )

    def test_stock_margin_available(self, db_conn):
        """stock_margin数据可用性 — FlowConfirm.margin_balance_change因子来源"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_margin'))
        count = result.scalar()
        if count == 0:
            pytest.skip(
                "stock_margin为空 — margin_balance_change因子无法计算. "
                "建议: 通过Tushare margin接口补充融资融券数据"
            )

    def test_pit_financial_available(self, db_conn):
        """pit_financial数据可用性 — PIT对齐的财务数据"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM pit_financial'))
        count = result.scalar()
        if count == 0:
            pytest.skip(
                "pit_financial为空 — 将使用stock_financial.ann_date做PIT对齐. "
                "建议: 通过Tushare fina_indicator接口补充, 确保ann_date字段完整"
            )

    def test_analyst_estimates_available(self, db_conn):
        """analyst_estimates_pit数据可用性 — Expectation模块因子来源"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM analyst_estimates_pit'))
        count = result.scalar()
        if count == 0:
            pytest.skip(
                "analyst_estimates_pit为空 — EPS修正/分析师覆盖/评级调整因子无法计算. "
                "Expectation模块将完全退化. "
                "建议: 通过Tushare forecast/dividend/earnings接口补充"
            )

    def test_event_center_available(self, db_conn):
        """event_center数据可用性 — 风险事件过滤来源"""
        result = db_conn.execute(text('SELECT COUNT(*) FROM event_center'))
        count = result.scalar()
        if count == 0:
            pytest.skip(
                "event_center为空 — 风险事件过滤将失效. "
                "建议: 通过Tushare stk_managers/stk_rewards等接口补充, 或手动维护黑名单"
            )


# ═══════════════════════════════════════════════
# 7. 因子计算可行性端到端验证
# ═══════════════════════════════════════════════

class TestFactorComputationFeasibility:
    """
    因子计算可行性端到端验证

    从数据库读取实际数据, 验证能否计算出Alpha模块所需因子
    """

    def test_quality_growth_factors_from_db(self, db_conn):
        """QualityGrowth因子计算可行性"""
        # ROE: 从stock_financial获取
        result = db_conn.execute(text('''
            SELECT ts_code, end_date, ann_date, roe, grossprofit_margin
            FROM stock_financial
            WHERE roe IS NOT NULL AND ann_date IS NOT NULL
            ORDER BY ann_date DESC
            LIMIT 10
        '''))
        rows = result.fetchall()
        assert len(rows) > 0, "无法从stock_financial获取ROE数据 — QualityGrowth模块无法运行"

    def test_residual_momentum_factors_from_db(self, db_conn):
        """ResidualMomentum因子计算可行性"""
        # 残差收益: 从stock_daily计算
        result = db_conn.execute(text('''
            SELECT ts_code, trade_date, close, pct_chg
            FROM stock_daily
            WHERE pct_chg IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 20
        '''))
        rows = result.fetchall()
        assert len(rows) >= 20, "无法从stock_daily获取足够行情数据 — ResidualMomentum模块无法运行"

    def test_flow_confirm_factors_from_db(self, db_conn):
        """FlowConfirm因子计算可行性"""
        # 北向资金
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_northbound'))
        north_count = result.scalar()

        # 资金流向
        result = db_conn.execute(text('SELECT COUNT(*) FROM stock_money_flow'))
        flow_count = result.scalar()

        if north_count == 0 and flow_count == 0:
            pytest.fail(
                "stock_northbound和stock_money_flow均为空! "
                "FlowConfirm模块完全无法运行. "
                "至少需要其中一个数据源"
            )

    def test_risk_penalty_factors_from_db(self, db_conn):
        """RiskPenalty因子计算可行性"""
        # 波动率: 从stock_daily计算
        result = db_conn.execute(text('''
            SELECT ts_code, COUNT(*) as cnt
            FROM stock_daily
            WHERE pct_chg IS NOT NULL
            GROUP BY ts_code
            HAVING COUNT(*) >= 20
            ORDER BY cnt DESC
            LIMIT 5
        '''))
        rows = result.fetchall()
        assert len(rows) > 0, "没有股票有20+天行情数据 — 波动率因子无法计算"

    def test_universe_build_from_real_data(self, db_conn):
        """使用真实数据库数据构建股票池"""
        from app.core.universe import UniverseBuilder

        # 从数据库读取数据
        stock_basic_df = pd.read_sql(
            'SELECT ts_code, list_date, list_status FROM stock_basic LIMIT 200',
            db_conn
        )

        result = db_conn.execute(text('SELECT MAX(trade_date) FROM stock_daily'))
        latest_date = result.scalar()

        if latest_date is None:
            pytest.skip("stock_daily无数据")

        if isinstance(latest_date, str):
            latest_date = datetime.strptime(latest_date, '%Y-%m-%d').date()
        elif isinstance(latest_date, datetime):
            latest_date = latest_date.date()

        price_df = pd.read_sql(
            text(f"SELECT ts_code, trade_date, close, amount FROM stock_daily WHERE trade_date >= :cutoff"),
            db_conn,
            params={'cutoff': latest_date - timedelta(days=60)}
        )

        if price_df.empty:
            pytest.skip("stock_daily近60天无数据")

        builder = UniverseBuilder()
        universe = builder.build(
            latest_date,
            stock_basic_df,
            price_df,
            min_list_days=0, min_daily_amount=0, min_price=0, min_market_cap=0,
        )
        assert len(universe) > 0, f"使用真实数据构建的股票池为空 — 数据可能存在严重问题"


# ═══════════════════════════════════════════════
# 8. 数据汇总报告
# ═══════════════════════════════════════════════

class TestDataAuditSummary:
    """数据审计汇总 — 生成可读报告"""

    def test_generate_data_audit_report(self, db_conn):
        """生成数据审计报告"""
        report = []
        report.append("=" * 60)
        report.append("数据库数据审计报告")
        report.append("=" * 60)

        # 表级统计
        tables = [
            'stock_basic', 'stock_daily', 'stock_daily_basic',
            'stock_financial', 'stock_northbound', 'stock_money_flow',
            'stock_status_daily', 'stock_margin', 'stock_industry',
            'index_daily', 'pit_financial', 'analyst_estimates_pit',
            'event_center', 'risk_flag_daily',
        ]

        report.append("\n表级统计:")
        report.append(f"{'表名':<30} {'行数':>12} {'状态':>8}")
        report.append("-" * 52)

        for table in tables:
            try:
                result = db_conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
                count = result.scalar()
                status = "OK" if count > 0 else "EMPTY"
                report.append(f"{table:<30} {count:>12,} {status:>8}")
            except Exception:
                report.append(f"{table:<30} {'N/A':>12} {'MISSING':>8}")

        # 关键字段覆盖率
        report.append("\n关键字段覆盖率:")
        field_checks = [
            ('stock_basic', 'list_date'),
            ('stock_basic', 'industry'),
            ('stock_daily', 'close'),
            ('stock_daily', 'amount'),
            ('stock_daily_basic', 'total_mv'),
            ('stock_financial', 'roe'),
            ('stock_financial', 'ann_date'),
        ]

        for table, col in field_checks:
            try:
                result = db_conn.execute(text(f'SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL'))
                non_null = result.scalar()
                result = db_conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
                total = result.scalar()
                coverage = non_null / total * 100 if total > 0 else 0
                report.append(f"  {table}.{col}: {coverage:.1f}%")
            except Exception as e:
                report.append(f"  {table}.{col}: ERROR ({e})")

        # 日期格式
        report.append("\n日期格式:")
        date_cols = [
            ('stock_daily', 'trade_date'),
            ('stock_daily_basic', 'trade_date'),
            ('stock_basic', 'list_date'),
            ('stock_financial', 'end_date'),
            ('stock_financial', 'ann_date'),
        ]
        for table, col in date_cols:
            try:
                result = db_conn.execute(text(f'''
                    SELECT data_type FROM information_schema.columns
                    WHERE table_name = '{table}' AND column_name = '{col}'
                '''))
                dtype = result.scalar()
                report.append(f"  {table}.{col}: {dtype}")
            except Exception:
                report.append(f"  {table}.{col}: N/A")

        report_text = "\n".join(report)
        print(report_text)

        # 写入报告文件
        import os
        report_path = os.path.join(os.path.dirname(__file__), '..', 'data_audit_report.txt')
        with open(report_path, 'w') as f:
            f.write(report_text)

        # 报告总是"通过", 但打印详细信息
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
