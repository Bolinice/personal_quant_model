"""支付订单模型"""
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base


class PaymentOrder(Base):
    """支付订单表"""

    __tablename__ = "payment_orders"

    id: int = Column(Integer, primary_key=True, index=True)
    order_no: str = Column(String(64), unique=True, index=True, nullable=False, comment="订单号")
    user_id: int = Column(Integer, index=True, nullable=False, comment="用户ID")
    subscription_id: int = Column(Integer, index=True, nullable=True, comment="订阅ID")
    plan_id: int = Column(Integer, nullable=True, comment="套餐ID")

    # 订单信息
    subject: str = Column(String(256), nullable=False, comment="订单标题")
    body: str = Column(Text, nullable=True, comment="订单描述")
    amount: float = Column(Float, nullable=False, comment="订单金额（元）")
    currency: str = Column(String(10), default="CNY", comment="货币类型")

    # 支付信息
    payment_method: str = Column(String(20), nullable=False, comment="支付方式: alipay, wechat")
    payment_type: str = Column(String(20), nullable=True, comment="支付类型: web, h5, native, jsapi")
    status: str = Column(
        String(20), default="pending", index=True, comment="订单状态: pending, paid, failed, cancelled, refunded"
    )

    # 第三方支付信息
    trade_no: str = Column(String(128), nullable=True, index=True, comment="第三方交易号")
    prepay_id: str = Column(String(128), nullable=True, comment="预支付ID（微信）")
    code_url: str = Column(String(512), nullable=True, comment="二维码URL（扫码支付）")
    h5_url: str = Column(String(512), nullable=True, comment="H5支付URL")

    # 支付时间
    paid_at: DateTime = Column(DateTime, nullable=True, comment="支付完成时间")
    expired_at: DateTime = Column(DateTime, nullable=True, comment="订单过期时间")

    # 回调信息
    notify_data: JSON = Column(JSON, nullable=True, comment="支付回调原始数据")
    notify_time: DateTime = Column(DateTime, nullable=True, comment="回调时间")

    # 退款信息
    refund_amount: float = Column(Float, default=0, comment="退款金额")
    refund_reason: str = Column(Text, nullable=True, comment="退款原因")
    refunded_at: DateTime = Column(DateTime, nullable=True, comment="退款时间")

    # 其他
    client_ip: str = Column(String(64), nullable=True, comment="客户端IP")
    extra_data: JSON = Column(JSON, nullable=True, comment="额外数据")

    created_at: DateTime = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<PaymentOrder(order_no='{self.order_no}', amount={self.amount}, status='{self.status}')>"


class PaymentConfig(Base):
    """支付配置表"""

    __tablename__ = "payment_configs"

    id: int = Column(Integer, primary_key=True, index=True)
    payment_method: str = Column(String(20), unique=True, nullable=False, comment="支付方式")
    is_enabled: bool = Column(Integer, default=1, comment="是否启用")

    # 配置信息（加密存储）
    app_id: str = Column(String(128), nullable=True, comment="应用ID")
    merchant_id: str = Column(String(128), nullable=True, comment="商户号")
    api_key: str = Column(Text, nullable=True, comment="API密钥")
    private_key: str = Column(Text, nullable=True, comment="私钥")
    public_key: str = Column(Text, nullable=True, comment="公钥")
    cert_path: str = Column(String(512), nullable=True, comment="证书路径")

    # 回调地址
    notify_url: str = Column(String(512), nullable=True, comment="异步回调地址")
    return_url: str = Column(String(512), nullable=True, comment="同步回调地址")

    # 其他配置
    config_data: JSON = Column(JSON, nullable=True, comment="其他配置")

    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<PaymentConfig(payment_method='{self.payment_method}', is_enabled={self.is_enabled})>"
