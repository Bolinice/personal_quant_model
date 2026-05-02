"""add_audit_logs_table

Revision ID: c1d2e3f4a5b6
Revises: ba222cea83cf
Create Date: 2026-05-03 02:56:17.729765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'ba222cea83cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 创建审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=True),
        sa.Column('resource_id', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('path', sa.String(length=500), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('extra_data', sa.Text(), nullable=True),
        sa.Column('previous_hash', sa.String(length=64), nullable=True),
        sa.Column('current_hash', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_current_hash'), 'audit_logs', ['current_hash'], unique=True)

    # 创建复合索引
    op.create_index('ix_audit_logs_user_time', 'audit_logs', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_audit_logs_action_time', 'audit_logs', ['action', 'created_at'], unique=False)
    op.create_index('ix_audit_logs_resource_time', 'audit_logs', ['resource_type', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 删除复合索引
    op.drop_index('ix_audit_logs_resource_time', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action_time', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_time', table_name='audit_logs')

    # 删除单列索引
    op.drop_index(op.f('ix_audit_logs_current_hash'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_resource_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')

    # 删除表
    op.drop_table('audit_logs')
