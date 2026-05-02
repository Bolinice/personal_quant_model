"""
数据库优化迁移脚本
添加外键约束、检查约束、缺失索引
"""

from alembic import op
import sqlalchemy as sa


def upgrade_add_foreign_keys():
    """添加外键约束"""

    print("添加外键约束...")

    # factor_values 外键
    op.create_foreign_key(
        'fk_fv_factor_id',
        'factor_values', 'factors',
        ['factor_id'], ['id'],
        ondelete='CASCADE'
    )
    print("✓ factor_values.factor_id → factors.id")

    # model_scores 外键
    op.create_foreign_key(
        'fk_ms_model_id',
        'model_scores', 'models',
        ['model_id'], ['id'],
        ondelete='CASCADE'
    )
    print("✓ model_scores.model_id → models.id")

    # backtest_results 外键
    op.create_foreign_key(
        'fk_br_backtest_id',
        'backtest_results', 'backtests',
        ['backtest_id'], ['id'],
        ondelete='CASCADE'
    )
    print("✓ backtest_results.backtest_id → backtests.id")

    # backtest_trades 外键
    op.create_foreign_key(
        'fk_bt_backtest_id',
        'backtest_trades', 'backtests',
        ['backtest_id'], ['id'],
        ondelete='CASCADE'
    )
    print("✓ backtest_trades.backtest_id → backtests.id")


def upgrade_add_check_constraints():
    """添加检查约束"""

    print("\n添加检查约束...")

    # StockDaily 检查约束
    op.create_check_constraint(
        'ck_sd_close_positive',
        'stock_daily',
        'close > 0'
    )
    print("✓ stock_daily.close > 0")

    op.create_check_constraint(
        'ck_sd_vol_non_negative',
        'stock_daily',
        'vol >= 0'
    )
    print("✓ stock_daily.vol >= 0")

    op.create_check_constraint(
        'ck_sd_pct_chg_range',
        'stock_daily',
        'pct_chg >= -20 AND pct_chg <= 20'
    )
    print("✓ stock_daily.pct_chg in [-20%, 20%]")

    # StockFinancial 检查约束（防止未来函数）
    op.create_check_constraint(
        'ck_sf_no_future_leak',
        'stock_financial',
        'ann_date >= end_date'
    )
    print("✓ stock_financial.ann_date >= end_date (防止未来函数)")

    # Backtest 检查约束
    op.create_check_constraint(
        'ck_bt_capital_positive',
        'backtests',
        'initial_capital > 0'
    )
    print("✓ backtests.initial_capital > 0")

    op.create_check_constraint(
        'ck_bt_commission_range',
        'backtests',
        'commission_rate >= 0 AND commission_rate <= 0.01'
    )
    print("✓ backtests.commission_rate in [0, 1%]")

    op.create_check_constraint(
        'ck_bt_holding_range',
        'backtests',
        'holding_count > 0 AND holding_count <= 1000'
    )
    print("✓ backtests.holding_count in [1, 1000]")

    # FactorValue 检查约束
    op.create_check_constraint(
        'ck_fv_coverage_flag',
        'factor_values',
        'coverage_flag IN (0, 1)'
    )
    print("✓ factor_values.coverage_flag in (0, 1)")


def upgrade_add_missing_indexes():
    """添加缺失的索引"""

    print("\n添加缺失的索引...")

    # PITFinancial 复合索引（最重要）
    op.create_index(
        'ix_pit_stock_ann_report',
        'pit_financial',
        ['stock_id', 'announce_date', 'report_period']
    )
    print("✓ pit_financial(stock_id, announce_date, report_period)")

    op.create_index(
        'ix_pit_stock_report_eff',
        'pit_financial',
        ['stock_id', 'report_period', 'effective_date']
    )
    print("✓ pit_financial(stock_id, report_period, effective_date)")

    # MonitorFactorHealth 索引
    op.create_index(
        'ix_mfh_factor_date',
        'monitor_factor_health',
        ['factor_name', 'trade_date']
    )
    print("✓ monitor_factor_health(factor_name, trade_date)")

    op.create_index(
        'ix_mfh_date_status',
        'monitor_factor_health',
        ['trade_date', 'health_status']
    )
    print("✓ monitor_factor_health(trade_date, health_status)")

    # ModelScore 索引
    op.create_index(
        'ix_ms_model_date_selected',
        'model_scores',
        ['model_id', 'trade_date', 'is_selected']
    )
    print("✓ model_scores(model_id, trade_date, is_selected)")

    op.create_index(
        'ix_ms_date_selected_score',
        'model_scores',
        ['trade_date', 'is_selected', 'score']
    )
    print("✓ model_scores(trade_date, is_selected, score)")

    # StockStatusDaily 索引
    op.create_index(
        'ix_ssd_date_code',
        'stock_status_daily',
        ['trade_date', 'ts_code']
    )
    print("✓ stock_status_daily(trade_date, ts_code)")

    op.create_index(
        'ix_ssd_code_date',
        'stock_status_daily',
        ['ts_code', 'trade_date']
    )
    print("✓ stock_status_daily(ts_code, trade_date)")

    # BacktestTrade 索引
    op.create_index(
        'ix_bt_trade_security',
        'backtest_trades',
        ['security_id', 'trade_date']
    )
    print("✓ backtest_trades(security_id, trade_date)")

    op.create_index(
        'ix_bt_trade_action',
        'backtest_trades',
        ['action', 'trade_date']
    )
    print("✓ backtest_trades(action, trade_date)")

    # StockDailyBasic 估值索引
    op.create_index(
        'ix_sdb_date_pe',
        'stock_daily_basic',
        ['trade_date', 'pe_ttm']
    )
    print("✓ stock_daily_basic(trade_date, pe_ttm)")

    op.create_index(
        'ix_sdb_date_pb',
        'stock_daily_basic',
        ['trade_date', 'pb']
    )
    print("✓ stock_daily_basic(trade_date, pb)")

    op.create_index(
        'ix_sdb_date_mv',
        'stock_daily_basic',
        ['trade_date', 'circ_mv']
    )
    print("✓ stock_daily_basic(trade_date, circ_mv)")


def downgrade_remove_foreign_keys():
    """回滚：删除外键约束"""
    op.drop_constraint('fk_fv_factor_id', 'factor_values')
    op.drop_constraint('fk_ms_model_id', 'model_scores')
    op.drop_constraint('fk_br_backtest_id', 'backtest_results')
    op.drop_constraint('fk_bt_backtest_id', 'backtest_trades')


def downgrade_remove_check_constraints():
    """回滚：删除检查约束"""
    op.drop_constraint('ck_sd_close_positive', 'stock_daily')
    op.drop_constraint('ck_sd_vol_non_negative', 'stock_daily')
    op.drop_constraint('ck_sd_pct_chg_range', 'stock_daily')
    op.drop_constraint('ck_sf_no_future_leak', 'stock_financial')
    op.drop_constraint('ck_bt_capital_positive', 'backtests')
    op.drop_constraint('ck_bt_commission_range', 'backtests')
    op.drop_constraint('ck_bt_holding_range', 'backtests')
    op.drop_constraint('ck_fv_coverage_flag', 'factor_values')


def downgrade_remove_indexes():
    """回滚：删除索引"""
    op.drop_index('ix_pit_stock_ann_report', 'pit_financial')
    op.drop_index('ix_pit_stock_report_eff', 'pit_financial')
    op.drop_index('ix_mfh_factor_date', 'monitor_factor_health')
    op.drop_index('ix_mfh_date_status', 'monitor_factor_health')
    op.drop_index('ix_ms_model_date_selected', 'model_scores')
    op.drop_index('ix_ms_date_selected_score', 'model_scores')
    op.drop_index('ix_ssd_date_code', 'stock_status_daily')
    op.drop_index('ix_ssd_code_date', 'stock_status_daily')
    op.drop_index('ix_bt_trade_security', 'backtest_trades')
    op.drop_index('ix_bt_trade_action', 'backtest_trades')
    op.drop_index('ix_sdb_date_pe', 'stock_daily_basic')
    op.drop_index('ix_sdb_date_pb', 'stock_daily_basic')
    op.drop_index('ix_sdb_date_mv', 'stock_daily_basic')


if __name__ == "__main__":
    print("="*60)
    print("  数据库优化迁移脚本")
    print("="*60)
    print("\n此脚本将执行以下操作：")
    print("1. 添加外键约束（4个）")
    print("2. 添加检查约束（8个）")
    print("3. 添加缺失索引（13个）")
    print("\n预期收益：")
    print("- PIT查询性能提升 50-80%")
    print("- 数据完整性得到保障")
    print("- 异常数据在写入时即被拦截")
    print("\n⚠️  注意：此操作会锁表，建议在低峰期执行")
    print("\n请手动创建Alembic迁移文件并执行：")
    print("  alembic revision -m 'add_constraints_and_indexes'")
    print("  # 将上述函数复制到迁移文件的upgrade()和downgrade()中")
    print("  alembic upgrade head")
