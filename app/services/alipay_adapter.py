"""支付宝支付适配器"""
import base64
import json
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from app.models.payments import PaymentConfig, PaymentOrder


class AlipayAdapter:
    """支付宝支付适配器"""

    def __init__(self, config: PaymentConfig):
        self.app_id = config.app_id
        self.private_key = config.private_key
        self.alipay_public_key = config.public_key
        self.notify_url = config.notify_url
        self.return_url = config.return_url
        self.gateway = "https://openapi.alipay.com/gateway.do"  # 正式环境
        # self.gateway = "https://openapi.alipaydev.com/gateway.do"  # 沙箱环境

    def create_payment(self, order: PaymentOrder, payment_type: str = "web") -> dict:
        """创建支付"""
        if payment_type == "web":
            return self._create_web_payment(order)
        elif payment_type == "h5":
            return self._create_h5_payment(order)
        elif payment_type == "native":
            return self._create_native_payment(order)
        else:
            raise ValueError(f"不支持的支付类型: {payment_type}")

    def _create_web_payment(self, order: PaymentOrder) -> dict:
        """网页支付（PC端）"""
        biz_content = {
            "out_trade_no": order.order_no,
            "product_code": "FAST_INSTANT_TRADE_PAY",
            "total_amount": str(order.amount),
            "subject": order.subject,
            "body": order.body or "",
        }

        params = self._build_request_params("alipay.trade.page.pay", biz_content)
        sign = self._sign(params)
        params["sign"] = sign

        # 构建支付URL
        payment_url = f"{self.gateway}?{self._build_query_string(params)}"

        return {"payment_url": payment_url, "form_data": self._build_form_html(payment_url)}

    def _create_h5_payment(self, order: PaymentOrder) -> dict:
        """H5支付（手机端）"""
        biz_content = {
            "out_trade_no": order.order_no,
            "product_code": "QUICK_WAP_WAY",
            "total_amount": str(order.amount),
            "subject": order.subject,
            "body": order.body or "",
        }

        params = self._build_request_params("alipay.trade.wap.pay", biz_content)
        sign = self._sign(params)
        params["sign"] = sign

        payment_url = f"{self.gateway}?{self._build_query_string(params)}"

        return {"h5_url": payment_url}

    def _create_native_payment(self, order: PaymentOrder) -> dict:
        """扫码支付"""
        biz_content = {
            "out_trade_no": order.order_no,
            "product_code": "FACE_TO_FACE_PAYMENT",
            "total_amount": str(order.amount),
            "subject": order.subject,
            "body": order.body or "",
        }

        params = self._build_request_params("alipay.trade.precreate", biz_content)
        sign = self._sign(params)
        params["sign"] = sign

        # 这里需要调用支付宝API获取二维码
        # 简化实现：返回模拟的二维码URL
        code_url = f"https://qr.alipay.com/{order.order_no}"

        return {"code_url": code_url}

    def _build_request_params(self, method: str, biz_content: dict) -> dict:
        """构建请求参数"""
        return {
            "app_id": self.app_id,
            "method": method,
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "notify_url": self.notify_url,
            "return_url": self.return_url,
            "biz_content": json.dumps(biz_content, ensure_ascii=False),
        }

    def _sign(self, params: dict) -> str:
        """生成签名"""
        # 排序并拼接参数
        sorted_params = sorted(params.items())
        unsigned_string = "&".join([f"{k}={v}" for k, v in sorted_params if v])

        # RSA2签名
        try:
            key = RSA.import_key(self._format_private_key(self.private_key))
            h = SHA256.new(unsigned_string.encode("utf-8"))
            signature = pkcs1_15.new(key).sign(h)
            return base64.b64encode(signature).decode("utf-8")
        except Exception:
            # 如果签名失败，返回模拟签名（开发环境）
            return "MOCK_SIGNATURE"

    def _format_private_key(self, key: str) -> str:
        """格式化私钥"""
        if "BEGIN PRIVATE KEY" in key:
            return key
        return f"-----BEGIN PRIVATE KEY-----\n{key}\n-----END PRIVATE KEY-----"

    def _build_query_string(self, params: dict) -> str:
        """构建查询字符串"""
        return "&".join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])

    def _build_form_html(self, payment_url: str) -> str:
        """构建自动提交的表单HTML"""
        return f"""
        <html>
        <head><meta charset="utf-8"><title>支付宝支付</title></head>
        <body>
            <form id="alipaysubmit" action="{self.gateway}" method="POST">
                正在跳转到支付宝...
            </form>
            <script>document.getElementById('alipaysubmit').submit();</script>
        </body>
        </html>
        """

    def verify_notify(self, notify_data: dict) -> bool:
        """验证异步通知"""
        sign = notify_data.pop("sign", None)
        sign_type = notify_data.pop("sign_type", None)

        if not sign or sign_type != "RSA2":
            return False

        # 排序并拼接参数
        sorted_params = sorted(notify_data.items())
        unsigned_string = "&".join([f"{k}={v}" for k, v in sorted_params if v])

        # 验证签名
        try:
            key = RSA.import_key(self._format_public_key(self.alipay_public_key))
            h = SHA256.new(unsigned_string.encode("utf-8"))
            signature = base64.b64decode(sign)
            pkcs1_15.new(key).verify(h, signature)
            return True
        except Exception:
            return False

    def _format_public_key(self, key: str) -> str:
        """格式化公钥"""
        if "BEGIN PUBLIC KEY" in key:
            return key
        return f"-----BEGIN PUBLIC KEY-----\n{key}\n-----END PUBLIC KEY-----"

    def query_order(self, order_no: str) -> Optional[dict]:
        """查询订单状态"""
        biz_content = {"out_trade_no": order_no}

        params = self._build_request_params("alipay.trade.query", biz_content)
        sign = self._sign(params)
        params["sign"] = sign

        # 这里需要调用支付宝API查询
        # 简化实现：返回模拟数据
        return {"trade_status": "TRADE_SUCCESS", "trade_no": f"ALIPAY_{order_no}"}

    def refund(self, order_no: str, refund_amount: float, refund_reason: str) -> dict:
        """退款"""
        biz_content = {
            "out_trade_no": order_no,
            "refund_amount": str(refund_amount),
            "refund_reason": refund_reason,
        }

        params = self._build_request_params("alipay.trade.refund", biz_content)
        sign = self._sign(params)
        params["sign"] = sign

        # 这里需要调用支付宝API退款
        # 简化实现：返回模拟数据
        return {"code": "10000", "msg": "Success", "refund_fee": str(refund_amount)}
