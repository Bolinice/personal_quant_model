"""支付API路由"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.models.payments import PaymentOrder
from app.schemas.payments import (
    PaymentNotifyRequest,
    PaymentOrderCreate,
    PaymentOrderDetail,
    PaymentOrderQuery,
    PaymentOrderResponse,
    RefundRequest,
    RefundResponse,
)
from app.services.alipay_adapter import AlipayAdapter
from app.services.payment_service import (
    cancel_order,
    create_payment_order,
    get_payment_config,
    get_payment_order,
    get_user_payment_orders,
    update_order_status,
)
from app.services.wechat_pay_adapter import WechatPayAdapter

router = APIRouter()


@router.post("/orders", response_model=PaymentOrderResponse)
def create_order(order_data: PaymentOrderCreate, db: Session = Depends(get_db)):
    """创建支付订单"""
    try:
        # 创建订单
        order = create_payment_order(order_data, db)

        # 获取支付配置
        config = get_payment_config(order_data.payment_method, db)
        if not config or not config.is_enabled:
            raise HTTPException(status_code=400, detail=f"支付方式 {order_data.payment_method} 未启用")

        # 调用支付接口
        payment_result = {}
        if order_data.payment_method == "alipay":
            adapter = AlipayAdapter(config)
            payment_result = adapter.create_payment(order, order_data.payment_type)
        elif order_data.payment_method == "wechat":
            adapter = WechatPayAdapter(config)
            payment_result = adapter.create_payment(order, order_data.payment_type)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的支付方式: {order_data.payment_method}")

        # 更新订单信息
        if "code_url" in payment_result:
            order.code_url = payment_result["code_url"]
        if "h5_url" in payment_result:
            order.h5_url = payment_result["h5_url"]
        if "prepay_id" in payment_result:
            order.prepay_id = payment_result["prepay_id"]

        db.commit()
        db.refresh(order)

        # 构建响应
        response = PaymentOrderResponse(
            order_no=order.order_no,
            amount=order.amount,
            subject=order.subject,
            payment_method=order.payment_method,
            payment_type=order.payment_type,
            status=order.status,
            code_url=order.code_url,
            h5_url=order.h5_url,
            form_data=payment_result.get("form_data"),
            prepay_id=order.prepay_id,
            expired_at=order.expired_at,
            created_at=order.created_at,
        )

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建订单失败: {str(e)}")


@router.get("/orders/{order_no}", response_model=PaymentOrderDetail)
def query_order(order_no: str, db: Session = Depends(get_db)):
    """查询订单详情"""
    order = get_payment_order(order_no, db)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return order


@router.get("/orders/user/{user_id}")
def get_user_orders(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """获取用户的订单列表"""
    orders = get_user_payment_orders(user_id, db, limit)
    return success([PaymentOrderDetail.model_validate(order) for order in orders])


@router.post("/orders/{order_no}/cancel")
def cancel_order_endpoint(order_no: str, db: Session = Depends(get_db)):
    """取消订单"""
    order = cancel_order(order_no, db)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return success({"order_no": order.order_no, "status": order.status})


@router.post("/notify/alipay")
async def alipay_notify(request: Request, db: Session = Depends(get_db)):
    """支付宝异步通知"""
    try:
        # 获取通知数据
        form_data = await request.form()
        notify_data = dict(form_data)

        # 获取订单号
        order_no = notify_data.get("out_trade_no")
        if not order_no:
            return "fail"

        order = get_payment_order(order_no, db)
        if not order:
            return "fail"

        # 验证签名
        config = get_payment_config("alipay", db)
        if config:
            adapter = AlipayAdapter(config)
            if not adapter.verify_notify(notify_data.copy()):
                return "fail"

        # 更新订单状态
        trade_status = notify_data.get("trade_status")
        if trade_status == "TRADE_SUCCESS" or trade_status == "TRADE_FINISHED":
            trade_no = notify_data.get("trade_no")
            update_order_status(order_no, "paid", trade_no, notify_data, db)

        return "success"

    except Exception as e:
        print(f"支付宝回调处理失败: {e}")
        return "fail"


@router.post("/notify/wechat")
async def wechat_notify(request: Request, db: Session = Depends(get_db)):
    """微信支付异步通知"""
    try:
        # 获取XML数据
        xml_data = await request.body()
        xml_str = xml_data.decode("utf-8")

        # 解析XML
        config = get_payment_config("wechat", db)
        if not config:
            return WechatPayAdapter(config).build_notify_response("FAIL", "配置不存在")

        adapter = WechatPayAdapter(config)
        notify_data = adapter.parse_notify_xml(xml_str)

        # 验证签名
        if not adapter.verify_notify(notify_data):
            return adapter.build_notify_response("FAIL", "签名验证失败")

        # 获取订单号
        order_no = notify_data.get("out_trade_no")
        if not order_no:
            return adapter.build_notify_response("FAIL", "订单号不存在")

        order = get_payment_order(order_no, db)
        if not order:
            return adapter.build_notify_response("FAIL", "订单不存在")

        # 更新订单状态
        result_code = notify_data.get("result_code")
        if result_code == "SUCCESS":
            trade_no = notify_data.get("transaction_id")
            update_order_status(order_no, "paid", trade_no, notify_data, db)

        return adapter.build_notify_response("SUCCESS", "OK")

    except Exception as e:
        print(f"微信回调处理失败: {e}")
        config = get_payment_config("wechat", db)
        if config:
            adapter = WechatPayAdapter(config)
            return adapter.build_notify_response("FAIL", str(e))
        return "FAIL"


@router.post("/refund", response_model=RefundResponse)
def refund_order(refund_data: RefundRequest, db: Session = Depends(get_db)):
    """退款"""
    order = get_payment_order(refund_data.order_no, db)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status != "paid":
        raise HTTPException(status_code=400, detail="订单状态不允许退款")

    # 计算退款金额
    refund_amount = refund_data.refund_amount or order.amount
    if refund_amount > order.amount - order.refund_amount:
        raise HTTPException(status_code=400, detail="退款金额超过可退款金额")

    # 调用退款接口
    config = get_payment_config(order.payment_method, db)
    if not config:
        raise HTTPException(status_code=400, detail="支付配置不存在")

    try:
        if order.payment_method == "alipay":
            adapter = AlipayAdapter(config)
            result = adapter.refund(order.order_no, refund_amount, refund_data.refund_reason)
        elif order.payment_method == "wechat":
            adapter = WechatPayAdapter(config)
            result = adapter.refund(order.order_no, refund_amount, refund_data.refund_reason)
        else:
            raise HTTPException(status_code=400, detail="不支持的支付方式")

        # 更新订单
        order.refund_amount += refund_amount
        order.refund_reason = refund_data.refund_reason
        if order.refund_amount >= order.amount:
            order.status = "refunded"
        db.commit()

        return RefundResponse(
            order_no=order.order_no,
            refund_amount=refund_amount,
            status=order.status,
            refunded_at=order.refunded_at,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"退款失败: {str(e)}")


@router.post("/mock/pay/{order_no}")
def mock_payment(order_no: str, db: Session = Depends(get_db)):
    """模拟支付成功（仅用于开发测试）"""
    order = get_payment_order(order_no, db)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status != "pending":
        raise HTTPException(status_code=400, detail="订单状态不允许支付")

    # 模拟支付成功
    trade_no = f"MOCK_{order.payment_method.upper()}_{order_no}"
    update_order_status(order_no, "paid", trade_no, {"mock": True}, db)

    return success({"order_no": order.order_no, "status": "paid", "trade_no": trade_no})
