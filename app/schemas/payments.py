"""支付相关的Pydantic模型"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PaymentOrderCreate(BaseModel):
    """创建支付订单请求"""

    user_id: int
    plan_id: int
    payment_method: str = Field(..., description="支付方式: alipay, wechat")
    payment_type: str = Field(..., description="支付类型: web, h5, native, jsapi")
    client_ip: Optional[str] = None
    return_url: Optional[str] = None


class PaymentOrderResponse(BaseModel):
    """支付订单响应"""

    order_no: str
    amount: float
    subject: str
    payment_method: str
    payment_type: str
    status: str

    # 支付信息（根据支付类型返回不同字段）
    code_url: Optional[str] = None  # 扫码支付二维码URL
    h5_url: Optional[str] = None  # H5支付跳转URL
    form_data: Optional[str] = None  # 网页支付表单HTML
    prepay_id: Optional[str] = None  # 微信预支付ID

    expired_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentOrderQuery(BaseModel):
    """查询支付订单"""

    order_no: str


class PaymentOrderDetail(BaseModel):
    """支付订单详情"""

    id: int
    order_no: str
    user_id: int
    subscription_id: Optional[int] = None
    plan_id: Optional[int] = None
    subject: str
    body: Optional[str] = None
    amount: float
    currency: str
    payment_method: str
    payment_type: Optional[str] = None
    status: str
    trade_no: Optional[str] = None
    paid_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentNotifyRequest(BaseModel):
    """支付回调通知（用于验证）"""

    payment_method: str
    notify_data: dict[str, Any]


class RefundRequest(BaseModel):
    """退款请求"""

    order_no: str
    refund_amount: Optional[float] = None  # 不填则全额退款
    refund_reason: str


class RefundResponse(BaseModel):
    """退款响应"""

    order_no: str
    refund_amount: float
    status: str
    refunded_at: Optional[datetime] = None


class PaymentConfigCreate(BaseModel):
    """创建支付配置"""

    payment_method: str
    is_enabled: bool = True
    app_id: Optional[str] = None
    merchant_id: Optional[str] = None
    api_key: Optional[str] = None
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    config_data: Optional[dict[str, Any]] = None


class PaymentConfigResponse(BaseModel):
    """支付配置响应（不返回敏感信息）"""

    id: int
    payment_method: str
    is_enabled: bool
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
