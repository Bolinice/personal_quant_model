"""微信支付适配器"""
import hashlib
import time
import xml.etree.ElementTree as ET
from typing import Optional

from app.models.payments import PaymentConfig, PaymentOrder


class WechatPayAdapter:
    """微信支付适配器"""

    def __init__(self, config: PaymentConfig):
        self.app_id = config.app_id
        self.mch_id = config.merchant_id
        self.api_key = config.api_key
        self.notify_url = config.notify_url
        self.gateway = "https://api.mch.weixin.qq.com"

    def create_payment(self, order: PaymentOrder, payment_type: str = "native") -> dict:
        """创建支付"""
        if payment_type == "native":
            return self._create_native_payment(order)
        elif payment_type == "h5":
            return self._create_h5_payment(order)
        elif payment_type == "jsapi":
            return self._create_jsapi_payment(order)
        else:
            raise ValueError(f"不支持的支付类型: {payment_type}")

    def _create_native_payment(self, order: PaymentOrder) -> dict:
        """扫码支付（Native）"""
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "nonce_str": self._generate_nonce_str(),
            "body": order.subject,
            "out_trade_no": order.order_no,
            "total_fee": str(int(order.amount * 100)),  # 单位：分
            "spbill_create_ip": order.client_ip or "127.0.0.1",
            "notify_url": self.notify_url,
            "trade_type": "NATIVE",
        }

        # 生成签名
        params["sign"] = self._sign(params)

        # 调用统一下单API
        # 简化实现：返回模拟的二维码URL
        code_url = f"weixin://wxpay/bizpayurl?pr={order.order_no}"

        return {"code_url": code_url, "prepay_id": f"wx{int(time.time())}"}

    def _create_h5_payment(self, order: PaymentOrder) -> dict:
        """H5支付"""
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "nonce_str": self._generate_nonce_str(),
            "body": order.subject,
            "out_trade_no": order.order_no,
            "total_fee": str(int(order.amount * 100)),
            "spbill_create_ip": order.client_ip or "127.0.0.1",
            "notify_url": self.notify_url,
            "trade_type": "MWEB",
            "scene_info": '{"h5_info": {"type":"Wap","wap_url": "https://example.com","wap_name": "量化策略平台"}}',
        }

        params["sign"] = self._sign(params)

        # 简化实现：返回模拟的H5支付URL
        h5_url = f"https://wx.tenpay.com/cgi-bin/mmpayweb-bin/checkmweb?prepay_id=wx{int(time.time())}"

        return {"h5_url": h5_url}

    def _create_jsapi_payment(self, order: PaymentOrder) -> dict:
        """JSAPI支付（公众号/小程序）"""
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "nonce_str": self._generate_nonce_str(),
            "body": order.subject,
            "out_trade_no": order.order_no,
            "total_fee": str(int(order.amount * 100)),
            "spbill_create_ip": order.client_ip or "127.0.0.1",
            "notify_url": self.notify_url,
            "trade_type": "JSAPI",
            "openid": order.extra_data.get("openid") if order.extra_data else None,
        }

        params["sign"] = self._sign(params)

        prepay_id = f"wx{int(time.time())}"

        # 生成JSAPI支付参数
        jsapi_params = {
            "appId": self.app_id,
            "timeStamp": str(int(time.time())),
            "nonceStr": self._generate_nonce_str(),
            "package": f"prepay_id={prepay_id}",
            "signType": "MD5",
        }
        jsapi_params["paySign"] = self._sign(jsapi_params)

        return {"prepay_id": prepay_id, "jsapi_params": jsapi_params}

    def _sign(self, params: dict) -> str:
        """生成签名"""
        # 过滤空值并排序
        filtered_params = {k: v for k, v in params.items() if v and k != "sign"}
        sorted_params = sorted(filtered_params.items())

        # 拼接字符串
        string_to_sign = "&".join([f"{k}={v}" for k, v in sorted_params])
        string_to_sign += f"&key={self.api_key}"

        # MD5签名
        sign = hashlib.md5(string_to_sign.encode("utf-8")).hexdigest().upper()
        return sign

    def _generate_nonce_str(self) -> str:
        """生成随机字符串"""
        return hashlib.md5(str(time.time()).encode()).hexdigest()

    def verify_notify(self, notify_data: dict) -> bool:
        """验证异步通知"""
        sign = notify_data.get("sign")
        if not sign:
            return False

        # 计算签名
        calculated_sign = self._sign(notify_data)

        return sign == calculated_sign

    def parse_notify_xml(self, xml_data: str) -> dict:
        """解析XML通知数据"""
        root = ET.fromstring(xml_data)
        return {child.tag: child.text for child in root}

    def build_notify_response(self, return_code: str = "SUCCESS", return_msg: str = "OK") -> str:
        """构建通知响应XML"""
        return f"""<xml>
  <return_code><![CDATA[{return_code}]]></return_code>
  <return_msg><![CDATA[{return_msg}]]></return_msg>
</xml>"""

    def query_order(self, order_no: str) -> Optional[dict]:
        """查询订单状态"""
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "out_trade_no": order_no,
            "nonce_str": self._generate_nonce_str(),
        }

        params["sign"] = self._sign(params)

        # 简化实现：返回模拟数据
        return {
            "return_code": "SUCCESS",
            "result_code": "SUCCESS",
            "trade_state": "SUCCESS",
            "transaction_id": f"WX{order_no}",
        }

    def refund(self, order_no: str, refund_amount: float, refund_reason: str) -> dict:
        """退款"""
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "nonce_str": self._generate_nonce_str(),
            "out_trade_no": order_no,
            "out_refund_no": f"REFUND_{order_no}_{int(time.time())}",
            "total_fee": str(int(refund_amount * 100)),
            "refund_fee": str(int(refund_amount * 100)),
            "refund_desc": refund_reason,
        }

        params["sign"] = self._sign(params)

        # 简化实现：返回模拟数据
        return {
            "return_code": "SUCCESS",
            "result_code": "SUCCESS",
            "refund_id": f"WXREFUND{int(time.time())}",
        }

    def close_order(self, order_no: str) -> dict:
        """关闭订单"""
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "out_trade_no": order_no,
            "nonce_str": self._generate_nonce_str(),
        }

        params["sign"] = self._sign(params)

        return {"return_code": "SUCCESS", "result_code": "SUCCESS"}
