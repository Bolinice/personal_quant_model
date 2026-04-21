"""
定价数据种子脚本 - 将订阅方案、价格矩阵、升级包写入数据库
用法: python scripts/seed_pricing.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import SessionLocal, engine
from app.models.products import SubscriptionPlan, PricingMatrix, UpgradePackage
from sqlalchemy import inspect


def seed_pricing():
    db = SessionLocal()
    try:
        # 确保表存在
        inspector = inspect(engine)
        Base = None
        for table_name in ['subscription_plans', 'pricing_matrix', 'upgrade_packages']:
            if table_name not in inspector.get_table_names():
                if Base is None:
                    from app.db.base import Base
                print(f"{table_name} 表不存在，正在创建...")
                Base.metadata.create_all(bind=engine)
                print("表创建完成")
                break

        # 清除旧数据
        db.query(UpgradePackage).delete()
        db.query(PricingMatrix).delete()
        db.query(SubscriptionPlan).delete()
        db.commit()

        # ==================== 订阅方案 ====================
        plans = [
            SubscriptionPlan(
                plan_name="基础版",
                plan_type="basic",
                plan_tier=1,
                price_monthly=299,
                price_yearly=1999,
                stock_pools=["沪深300", "中证500"],
                frequencies=["Monthly", "Biweekly"],
                features=[
                    "模型组合结果查看",
                    "基础历史表现展示",
                    "调仓记录摘要",
                    "组合收益/回撤等核心指标",
                    "基础风格与风险提示",
                ],
                description="适合初次使用量化模型的投资者",
                highlight=False,
                buttons=["立即体验", "查看样例"],
                is_active=True,
            ),
            SubscriptionPlan(
                plan_name="进阶版",
                plan_type="advanced",
                plan_tier=2,
                price_monthly=799,
                price_yearly=6999,
                stock_pools=["沪深300", "中证500", "中证1000"],
                frequencies=["Monthly", "Biweekly", "Weekly"],
                features=[
                    "完整模型组合结果",
                    "更完整的历史统计分析",
                    "调仓记录与组合变化跟踪",
                    "胜率、回撤、波动等指标展示",
                    "部分数据导出",
                    "组合风格与行业分布分析",
                ],
                description="适合有一定研究基础的个人投资者",
                highlight=True,
                buttons=["推荐选择", "立即订阅"],
                is_active=True,
            ),
            SubscriptionPlan(
                plan_name="专业版",
                plan_type="professional",
                plan_tier=3,
                price_monthly=1999,
                price_yearly=15999,
                stock_pools=["沪深300", "中证500", "中证1000", "全A"],
                frequencies=["Daily", "Weekly", "Biweekly", "Monthly"],
                features=[
                    "全量股票池模型研究结果",
                    "全频率调仓方案查看",
                    "完整历史表现与统计分析",
                    "因子暴露与组合特征分析",
                    "数据导出权限",
                    "API 接口访问（标准配额）",
                    "组合跟踪与提醒服务",
                    "优先支持服务",
                ],
                description="适合高净值用户、职业投资者与研究型用户",
                highlight=False,
                buttons=["专业用户首选", "申请试用"],
                is_active=True,
            ),
            SubscriptionPlan(
                plan_name="团队版",
                plan_type="team",
                plan_tier=4,
                price_yearly=69800,
                price_unit="元/年起",
                stock_pools=["全部股票池"],
                frequencies=["全部频率"],
                features=[
                    "多账号权限管理",
                    "API 更高调用额度",
                    "全量历史数据",
                    "研究月报与版本更新说明",
                    "专属客户支持",
                    "可选简单参数配置",
                ],
                description="适合小型量化团队、投研团队、私募工作室",
                highlight=False,
                buttons=["联系销售", "预约演示"],
                is_active=True,
            ),
            SubscriptionPlan(
                plan_name="机构版",
                plan_type="enterprise",
                plan_tier=5,
                price_yearly=128000,
                price_unit="元/年起",
                custom_price="私有化及定制项目：面议",
                stock_pools=["全部+定制"],
                frequencies=["全部频率"],
                features=[
                    "专属 API",
                    "更高并发与SLA支持",
                    "指定股票池/模型定制",
                    "白标合作可选",
                    "私有化部署可选",
                    "专属研究支持与培训服务",
                ],
                description="适合私募、资管、券商、金融科技平台等机构客户",
                highlight=False,
                buttons=["获取方案", "商务咨询"],
                is_active=True,
            ),
        ]

        # ==================== 价格矩阵 ====================
        matrices = [
            PricingMatrix(
                billing_cycle="yearly",
                pools=["沪深300", "中证500", "中证1000", "全A"],
                frequencies=["Monthly", "Biweekly", "Weekly", "Daily"],
                prices=[
                    [999, 1499, 2499, 4999],
                    [1299, 1999, 2999, 5999],
                    [1999, 2999, 4599, 7999],
                    [2999, 3999, 5999, 9999],
                ],
                note="单模型适合测试特定股票池或调仓节奏，多模型组合购买可享阶梯折扣，建议优先选择标准套餐，整体性价比更高。",
                is_active=True,
            ),
            PricingMatrix(
                billing_cycle="monthly",
                pools=["沪深300", "中证500", "中证1000", "全A"],
                frequencies=["Monthly", "Biweekly", "Weekly", "Daily"],
                prices=[
                    [149, 199, 299, 599],
                    [199, 299, 399, 699],
                    [299, 399, 599, 999],
                    [399, 599, 799, 1299],
                ],
                note="单模型适合测试特定股票池或调仓节奏，多模型组合购买可享阶梯折扣，建议优先选择标准套餐，整体性价比更高。",
                is_active=True,
            ),
        ]

        # ==================== 升级包 ====================
        packages = [
            UpgradePackage(
                name="全A升级包",
                description="在现有版本基础上增加全A股票池研究权限",
                price_monthly=300,
                price_yearly=3000,
                sort_order=1,
                is_active=True,
            ),
            UpgradePackage(
                name="Daily频率升级包",
                description="在现有版本基础上增加日频调仓模型权限",
                price_monthly=500,
                price_yearly=5000,
                sort_order=2,
                is_active=True,
            ),
            UpgradePackage(
                name="API升级包",
                description="适合需要程序化接入或批量研究的用户",
                price_standard="500元/月",
                price_advanced="2000元/月起",
                sort_order=3,
                is_active=True,
            ),
            UpgradePackage(
                name="多席位升级包",
                description="适合团队共同使用",
                price_yearly=8000,
                price_unit="元/席位/年起",
                sort_order=4,
                is_active=True,
            ),
        ]

        # 写入数据库
        for plan in plans:
            db.add(plan)
        for matrix in matrices:
            db.add(matrix)
        for pkg in packages:
            db.add(pkg)

        db.commit()
        print(f"成功写入 {len(plans)} 个订阅方案, {len(matrices)} 个价格矩阵, {len(packages)} 个升级包")

    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_pricing()
