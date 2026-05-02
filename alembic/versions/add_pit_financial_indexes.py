"""add pit_financial indexes

Revision ID: add_pit_financial_indexes
Revises: add_payment_tables
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_pit_financial_indexes'
down_revision = 'add_payment_tables'
branch_labels = None
depends_on = None


def upgrade():
    """添加PITFinancial表的关键复合索引"""

    # 1. 最关键的索引：(stock_id, report_period, announce_date)
    # 用于PIT查询：给定股票和报告期，找到特定日期前的最新数据
    op.create_index(
        'ix_pit_financial_stock_report_announce',
        'pit_financial',
        ['stock_id', 'report_period', 'announce_date'],
        unique=False
    )

    # 2. 时间范围查询索引：(announce_date, stock_id)
    # 用于批量获取某个时间段的所有股票财务数据
    op.create_index(
        'ix_pit_financial_announce_stock',
        'pit_financial',
        ['announce_date', 'stock_id'],
        unique=False
    )

    # 3. 报告期查询索引：(report_period, stock_id, announce_date)
    # 用于查询特定报告期的所有股票数据
    op.create_index(
        'ix_pit_financial_report_stock_announce',
        'pit_financial',
        ['report_period', 'stock_id', 'announce_date'],
        unique=False
    )

    # 4. 快照查询索引：(snapshot_id, stock_id)
    # 用于快速检索特定快照的数据
    op.create_index(
        'ix_pit_financial_snapshot_stock',
        'pit_financial',
        ['snapshot_id', 'stock_id'],
        unique=False
    )


def downgrade():
    """删除添加的索引"""
    op.drop_index('ix_pit_financial_snapshot_stock', table_name='pit_financial')
    op.drop_index('ix_pit_financial_report_stock_announce', table_name='pit_financial')
    op.drop_index('ix_pit_financial_announce_stock', table_name='pit_financial')
    op.drop_index('ix_pit_financial_stock_report_announce', table_name='pit_financial')
