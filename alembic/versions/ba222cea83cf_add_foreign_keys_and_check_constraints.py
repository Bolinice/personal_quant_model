"""add_foreign_keys_and_check_constraints

Revision ID: ba222cea83cf
Revises: add_pit_financial_indexes
Create Date: 2026-05-02 20:44:27.905105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba222cea83cf'
down_revision: Union[str, Sequence[str], None] = 'add_pit_financial_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add foreign key constraints
    # Factor-related tables
    op.create_foreign_key('fk_factor_values_factor_id', 'factor_values', 'factors', ['factor_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_factor_analysis_factor_id', 'factor_analysis', 'factors', ['factor_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_factor_results_factor_id', 'factor_results', 'factors', ['factor_id'], ['id'], ondelete='CASCADE')

    # Model-related tables
    op.create_foreign_key('fk_model_factor_weights_model_id', 'model_factor_weights', 'models', ['model_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_model_factor_weights_factor_id', 'model_factor_weights', 'factors', ['factor_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_model_scores_model_id', 'model_scores', 'models', ['model_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_model_performance_model_id', 'model_performance', 'models', ['model_id'], ['id'], ondelete='CASCADE')

    # Backtest-related tables
    op.create_foreign_key('fk_backtests_model_id', 'backtests', 'models', ['model_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_backtest_navs_backtest_id', 'backtest_navs', 'backtests', ['backtest_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_backtest_positions_backtest_id', 'backtest_positions', 'backtests', ['backtest_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_backtest_trades_backtest_id', 'backtest_trades', 'backtests', ['backtest_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_backtest_results_backtest_id', 'backtest_results', 'backtests', ['backtest_id'], ['id'], ondelete='CASCADE')

    # Add check constraints
    # Factor direction must be 1 or -1
    op.create_check_constraint('ck_factors_direction', 'factors', 'direction IN (1, -1)')

    # Model status must be valid
    op.create_check_constraint('ck_models_status', 'models', "status IN ('draft', 'active', 'archived')")

    # Backtest status must be valid
    op.create_check_constraint('ck_backtests_status', 'backtests', "status IN ('pending', 'running', 'success', 'failed')")

    # Backtest progress must be between 0 and 100
    op.create_check_constraint('ck_backtests_progress', 'backtests', 'progress >= 0 AND progress <= 100')

    # Backtest execution mode must be valid
    op.create_check_constraint('ck_backtests_execution_mode', 'backtests', "execution_mode IN ('open', 'vwap', 'close')")

    # Backtest rebalance frequency must be valid
    op.create_check_constraint('ck_backtests_rebalance_freq', 'backtests', "rebalance_freq IN ('daily', 'weekly', 'biweekly', 'monthly')")

    # Backtest holding count must be positive
    op.create_check_constraint('ck_backtests_holding_count', 'backtests', 'holding_count > 0')

    # Backtest initial capital must be positive
    op.create_check_constraint('ck_backtests_initial_capital', 'backtests', 'initial_capital > 0')

    # Trade action must be buy or sell
    op.create_check_constraint('ck_backtest_trades_action', 'backtest_trades', "action IN ('buy', 'sell')")

    # Trade quantity must be positive
    op.create_check_constraint('ck_backtest_trades_quantity', 'backtest_trades', 'quantity > 0')

    # Trade status must be valid
    op.create_check_constraint('ck_backtest_trades_status', 'backtest_trades', "trade_status IN ('success', 'failed')")

    # Model factor weight direction must be 1 or -1
    op.create_check_constraint('ck_model_factor_weights_direction', 'model_factor_weights', 'direction IN (1, -1)')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop check constraints
    op.drop_constraint('ck_model_factor_weights_direction', 'model_factor_weights', type_='check')
    op.drop_constraint('ck_backtest_trades_status', 'backtest_trades', type_='check')
    op.drop_constraint('ck_backtest_trades_quantity', 'backtest_trades', type_='check')
    op.drop_constraint('ck_backtest_trades_action', 'backtest_trades', type_='check')
    op.drop_constraint('ck_backtests_initial_capital', 'backtests', type_='check')
    op.drop_constraint('ck_backtests_holding_count', 'backtests', type_='check')
    op.drop_constraint('ck_backtests_rebalance_freq', 'backtests', type_='check')
    op.drop_constraint('ck_backtests_execution_mode', 'backtests', type_='check')
    op.drop_constraint('ck_backtests_progress', 'backtests', type_='check')
    op.drop_constraint('ck_backtests_status', 'backtests', type_='check')
    op.drop_constraint('ck_models_status', 'models', type_='check')
    op.drop_constraint('ck_factors_direction', 'factors', type_='check')

    # Drop foreign key constraints
    op.drop_constraint('fk_backtest_results_backtest_id', 'backtest_results', type_='foreignkey')
    op.drop_constraint('fk_backtest_trades_backtest_id', 'backtest_trades', type_='foreignkey')
    op.drop_constraint('fk_backtest_positions_backtest_id', 'backtest_positions', type_='foreignkey')
    op.drop_constraint('fk_backtest_navs_backtest_id', 'backtest_navs', type_='foreignkey')
    op.drop_constraint('fk_backtests_model_id', 'backtests', type_='foreignkey')
    op.drop_constraint('fk_model_performance_model_id', 'model_performance', type_='foreignkey')
    op.drop_constraint('fk_model_scores_model_id', 'model_scores', type_='foreignkey')
    op.drop_constraint('fk_model_factor_weights_factor_id', 'model_factor_weights', type_='foreignkey')
    op.drop_constraint('fk_model_factor_weights_model_id', 'model_factor_weights', type_='foreignkey')
    op.drop_constraint('fk_factor_results_factor_id', 'factor_results', type_='foreignkey')
    op.drop_constraint('fk_factor_analysis_factor_id', 'factor_analysis', type_='foreignkey')
    op.drop_constraint('fk_factor_values_factor_id', 'factor_values', type_='foreignkey')
