"""添加支付相关表

Revision ID: add_payment_tables
Revises: 505b9b5bc8ac
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_payment_tables'
down_revision = '505b9b5bc8ac'
branch_labels = None
depends_on = None


def upgrade():
    # 创建支付订单表
    op.create_table(
        'payment_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_no', sa.String(length=64), nullable=False, comment='订单号'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='用户ID'),
        sa.Column('subscription_id', sa.Integer(), nullable=True, comment='订阅ID'),
        sa.Column('plan_id', sa.Integer(), nullable=True, comment='套餐ID'),
        sa.Column('subject', sa.String(length=256), nullable=False, comment='订单标题'),
        sa.Column('body', sa.Text(), nullable=True, comment='订单描述'),
        sa.Column('amount', sa.Float(), nullable=False, comment='订单金额（元）'),
        sa.Column('currency', sa.String(length=10), nullable=True, comment='货币类型'),
        sa.Column('payment_method', sa.String(length=20), nullable=False, comment='支付方式'),
        sa.Column('payment_type', sa.String(length=20), nullable=True, comment='支付类型'),
        sa.Column('status', sa.String(length=20), nullable=True, comment='订单状态'),
        sa.Column('trade_no', sa.String(length=128), nullable=True, comment='第三方交易号'),
        sa.Column('prepay_id', sa.String(length=128), nullable=True, comment='预支付ID'),
        sa.Column('code_url', sa.String(length=512), nullable=True, comment='二维码URL'),
        sa.Column('h5_url', sa.String(length=512), nullable=True, comment='H5支付URL'),
        sa.Column('paid_at', sa.DateTime(), nullable=True, comment='支付完成时间'),
        sa.Column('expired_at', sa.DateTime(), nullable=True, comment='订单过期时间'),
        sa.Column('notify_data', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='支付回调原始数据'),
        sa.Column('notify_time', sa.DateTime(), nullable=True, comment='回调时间'),
        sa.Column('refund_amount', sa.Float(), nullable=True, comment='退款金额'),
        sa.Column('refund_reason', sa.Text(), nullable=True, comment='退款原因'),
        sa.Column('refunded_at', sa.DateTime(), nullable=True, comment='退款时间'),
        sa.Column('client_ip', sa.String(length=64), nullable=True, comment='客户端IP'),
        sa.Column('extra_data', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='额外数据'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_orders_id'), 'payment_orders', ['id'], unique=False)
    op.create_index(op.f('ix_payment_orders_order_no'), 'payment_orders', ['order_no'], unique=True)
    op.create_index(op.f('ix_payment_orders_user_id'), 'payment_orders', ['user_id'], unique=False)
    op.create_index(op.f('ix_payment_orders_subscription_id'), 'payment_orders', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_payment_orders_status'), 'payment_orders', ['status'], unique=False)
    op.create_index(op.f('ix_payment_orders_trade_no'), 'payment_orders', ['trade_no'], unique=False)

    # 创建支付配置表
    op.create_table(
        'payment_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_method', sa.String(length=20), nullable=False, comment='支付方式'),
        sa.Column('is_enabled', sa.Integer(), nullable=True, comment='是否启用'),
        sa.Column('app_id', sa.String(length=128), nullable=True, comment='应用ID'),
        sa.Column('merchant_id', sa.String(length=128), nullable=True, comment='商户号'),
        sa.Column('api_key', sa.Text(), nullable=True, comment='API密钥'),
        sa.Column('private_key', sa.Text(), nullable=True, comment='私钥'),
        sa.Column('public_key', sa.Text(), nullable=True, comment='公钥'),
        sa.Column('cert_path', sa.String(length=512), nullable=True, comment='证书路径'),
        sa.Column('notify_url', sa.String(length=512), nullable=True, comment='异步回调地址'),
        sa.Column('return_url', sa.String(length=512), nullable=True, comment='同步回调地址'),
        sa.Column('config_data', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='其他配置'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_method')
    )
    op.create_index(op.f('ix_payment_configs_id'), 'payment_configs', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_payment_configs_id'), table_name='payment_configs')
    op.drop_table('payment_configs')

    op.drop_index(op.f('ix_payment_orders_trade_no'), table_name='payment_orders')
    op.drop_index(op.f('ix_payment_orders_status'), table_name='payment_orders')
    op.drop_index(op.f('ix_payment_orders_subscription_id'), table_name='payment_orders')
    op.drop_index(op.f('ix_payment_orders_user_id'), table_name='payment_orders')
    op.drop_index(op.f('ix_payment_orders_order_no'), table_name='payment_orders')
    op.drop_index(op.f('ix_payment_orders_id'), table_name='payment_orders')
    op.drop_table('payment_orders')
