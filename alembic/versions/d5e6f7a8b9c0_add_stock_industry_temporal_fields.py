"""add_stock_industry_temporal_fields

Revision ID: d5e6f7a8b9c0
Revises: c1d2e3f4a5b6
Create Date: 2026-05-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加行业分类历史时点字段"""
    # 添加 effective_date 字段
    op.add_column(
        'stock_industry',
        sa.Column('effective_date', sa.Date(), nullable=True, comment='生效日期')
    )

    # 添加 expire_date 字段
    op.add_column(
        'stock_industry',
        sa.Column('expire_date', sa.Date(), nullable=True, comment='失效日期，NULL表示当前有效')
    )

    # 创建索引以优化历史时点查询
    op.create_index(
        'ix_stock_industry_effective_date',
        'stock_industry',
        ['effective_date']
    )

    op.create_index(
        'ix_stock_industry_expire_date',
        'stock_industry',
        ['expire_date']
    )

    # 创建复合索引以优化时点查询性能
    op.create_index(
        'ix_stock_industry_ts_code_dates',
        'stock_industry',
        ['ts_code', 'effective_date', 'expire_date']
    )


def downgrade() -> None:
    """回滚行业分类历史时点字段"""
    # 删除复合索引
    op.drop_index('ix_stock_industry_ts_code_dates', table_name='stock_industry')

    # 删除单列索引
    op.drop_index('ix_stock_industry_expire_date', table_name='stock_industry')
    op.drop_index('ix_stock_industry_effective_date', table_name='stock_industry')

    # 删除字段
    op.drop_column('stock_industry', 'expire_date')
    op.drop_column('stock_industry', 'effective_date')
