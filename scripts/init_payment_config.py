"""初始化支付配置到数据库"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.payments import PaymentConfig


def init_payment_configs():
    """初始化支付配置"""
    db: Session = SessionLocal()

    try:
        # 支付宝配置
        if settings.ALIPAY_APP_ID:
            alipay_config = db.query(PaymentConfig).filter(PaymentConfig.payment_method == "alipay").first()

            if alipay_config:
                print("更新支付宝配置...")
                alipay_config.app_id = settings.ALIPAY_APP_ID
                alipay_config.private_key = settings.ALIPAY_PRIVATE_KEY
                alipay_config.public_key = settings.ALIPAY_PUBLIC_KEY
                alipay_config.notify_url = settings.ALIPAY_NOTIFY_URL
                alipay_config.return_url = settings.ALIPAY_RETURN_URL
                alipay_config.is_enabled = True
                alipay_config.config_data = {"gateway": settings.ALIPAY_GATEWAY}
            else:
                print("创建支付宝配置...")
                alipay_config = PaymentConfig(
                    payment_method="alipay",
                    app_id=settings.ALIPAY_APP_ID,
                    private_key=settings.ALIPAY_PRIVATE_KEY,
                    public_key=settings.ALIPAY_PUBLIC_KEY,
                    notify_url=settings.ALIPAY_NOTIFY_URL,
                    return_url=settings.ALIPAY_RETURN_URL,
                    is_enabled=True,
                    config_data={"gateway": settings.ALIPAY_GATEWAY},
                )
                db.add(alipay_config)

            db.commit()
            print("✓ 支付宝配置已保存")
        else:
            print("⚠ 支付宝配置未设置，跳过")

        # 微信支付配置
        if settings.WECHAT_APP_ID:
            wechat_config = db.query(PaymentConfig).filter(PaymentConfig.payment_method == "wechat").first()

            if wechat_config:
                print("更新微信支付配置...")
                wechat_config.app_id = settings.WECHAT_APP_ID
                wechat_config.merchant_id = settings.WECHAT_MCH_ID
                wechat_config.api_key = settings.WECHAT_API_KEY
                wechat_config.cert_path = settings.WECHAT_CERT_PATH
                wechat_config.notify_url = settings.WECHAT_NOTIFY_URL
                wechat_config.is_enabled = True
                wechat_config.config_data = {"key_path": settings.WECHAT_KEY_PATH}
            else:
                print("创建微信支付配置...")
                wechat_config = PaymentConfig(
                    payment_method="wechat",
                    app_id=settings.WECHAT_APP_ID,
                    merchant_id=settings.WECHAT_MCH_ID,
                    api_key=settings.WECHAT_API_KEY,
                    cert_path=settings.WECHAT_CERT_PATH,
                    notify_url=settings.WECHAT_NOTIFY_URL,
                    is_enabled=True,
                    config_data={"key_path": settings.WECHAT_KEY_PATH},
                )
                db.add(wechat_config)

            db.commit()
            print("✓ 微信支付配置已保存")
        else:
            print("⚠ 微信支付配置未设置，跳过")

        print("\n支付配置初始化完成！")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("开始初始化支付配置...")
    init_payment_configs()
