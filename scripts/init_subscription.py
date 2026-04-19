"""
初始化订阅产品和套餐
用法: python scripts/init_subscription.py
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from app.core.config import settings


def main():
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # 创建产品 (匹配 products 表结构: model_id, product_code, product_name, product_type, display_name, description, risk_level, status)
        products = [
            (3, 'ZZ1000_REPORT', '中证1000策略报告', 'report', '中证1000增强策略', '中证1000增强策略完整报告', 'medium', 'online'),
            (4, 'ALL_A_REPORT', '全A股策略报告', 'report', '全A股增强策略', '全A股增强策略完整报告', 'high', 'online'),
        ]
        for model_id, code, name, ptype, display, desc, risk, st in products:
            existing = conn.execute(text(
                "SELECT id FROM products WHERE product_code = :code"
            ), {'code': code}).fetchone()
            if not existing:
                conn.execute(text(
                    "INSERT INTO products (model_id, product_code, product_name, product_type, display_name, description, risk_level, status, is_active) "
                    "VALUES (:mid, :code, :name, :type, :display, :desc, :risk, :status, 1)"
                ), {'mid': model_id, 'code': code, 'name': name, 'type': ptype, 'display': display, 'desc': desc, 'risk': risk, 'status': st})
                print(f"  创建产品: {name}")
            else:
                print(f"  产品已存在: {name}")

        conn.commit()

        # 创建订阅套餐 (匹配 subscription_plans 表结构: plan_name, plan_type, price, duration_days, features)
        existing_plan = conn.execute(text(
            "SELECT id FROM subscription_plans WHERE plan_name = '策略报告专业版'"
        )).fetchone()
        if not existing_plan:
            conn.execute(text(
                "INSERT INTO subscription_plans (plan_name, plan_type, price, duration_days, features, is_active) "
                "VALUES (:name, :type, :price, :days, :features, 1)"
            ), {
                'name': '策略报告专业版',
                'type': 'month',
                'price': 199,
                'days': 30,
                'features': '["中证1000增强策略完整报告","全A股增强策略完整报告","每日持仓评分与排名","策略表现与风险指标","IC/换手率等核心数据"]',
            })
            print("  创建套餐: 策略报告专业版 ¥199/月")
        else:
            print("  套餐已存在: 策略报告专业版")

        conn.commit()
        print("\n完成!")


if __name__ == '__main__':
    main()