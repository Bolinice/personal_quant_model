"""
创建全能增强组合模板策略
综合利用多维度因子进行最佳决策
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.models import Model

def create_all_weather_template():
    """创建全能增强组合模板"""

    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 检查是否已存在
        existing = session.query(Model).filter_by(model_code="TEMPLATE_ALL_WEATHER").first()

        if existing:
            print("全能增强组合模板已存在，更新配置...")
            model = existing
        else:
            print("创建全能增强组合模板...")
            model = Model(
                model_code="TEMPLATE_ALL_WEATHER",
                model_type="scoring",
                version="1.0",
                status="active",
                is_default=True,
                created_by=None,
            )

        # 配置全能增强组合
        # 策略思路：多维度因子组合，平衡进攻与防守
        model.model_name = "全能增强组合"
        model.description = "综合基本面、技术面、资金面、风险面的多维度因子，构建攻守兼备的全天候策略"
        model.model_config = {
            # 核心因子组：覆盖基本面、技术面、资金面
            "factor_groups": [
                "valuation",           # 价值因子（5个）- 寻找低估值
                "growth",              # 成长因子（4个）- 寻找高成长
                "quality",             # 质量因子（5个）- 筛选优质公司
                "momentum",            # 动量因子（4个）- 捕捉趋势
                "earnings_quality",    # 盈利质量（4个）- 识别真实盈利
                "smart_money",         # 聪明钱因子（4个）- 跟随机构资金
                "northbound",          # 北向资金（3个）- A股重要资金指标
                "sentiment",           # 情绪因子（3个）- 市场情绪判断
                "volatility",          # 波动率因子（4个）- 风险控制
                "liquidity",           # 流动性因子（4个）- 确保可交易性
                "ashare_specific",     # A股特有（4个）- 规避ST等风险
            ],

            # 因子加权方法
            "weighting_method": "equal_weight",  # 等权重（稳健）

            # 中性化设置
            "neutralize_industry": True,   # 行业中性化，避免行业集中
            "neutralize_market_cap": True, # 市值中性化，避免市值偏向

            # 组合参数
            "top_n": 50,  # 持仓50只，分散风险
            "rebalance_freq": "monthly",  # 月度调仓

            # 风险控制
            "max_single_position": 0.05,  # 单只股票最大5%
            "max_industry_exposure": 0.25, # 单行业最大25%

            # 标记为模板
            "is_template": True,

            # 策略特点
            "strategy_features": [
                "多维度因子覆盖",
                "基本面与技术面结合",
                "资金面跟踪",
                "风险控制完善",
                "行业市值中性",
                "全天候适应性"
            ],

            # 适用场景
            "suitable_for": [
                "追求稳健收益的投资者",
                "希望全面覆盖多种alpha来源",
                "注重风险控制",
                "中长期持有"
            ],

            # 因子维度统计
            "factor_dimensions": {
                "基本面": ["valuation", "growth", "quality", "earnings_quality"],
                "技术面": ["momentum"],
                "资金面": ["smart_money", "northbound", "sentiment"],
                "风险面": ["volatility", "liquidity"],
                "特色面": ["ashare_specific"]
            },

            # 总因子数
            "total_factors": 44,  # 5+4+5+4+4+4+3+3+4+4+4 = 44个因子
        }

        session.add(model)
        session.commit()

        print(f"✓ 全能增强组合模板创建成功 (ID: {model.id})")
        print(f"  模型代码: {model.model_code}")
        print(f"  因子组数: {len(model.model_config['factor_groups'])}")
        print(f"  总因子数: {model.model_config['total_factors']}")
        print(f"  持仓数量: {model.model_config['top_n']}")
        print(f"\n策略特点:")
        for feature in model.model_config['strategy_features']:
            print(f"  • {feature}")

        return model.id

    except Exception as e:
        session.rollback()
        print(f"✗ 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 80)
    print("创建全能增强组合模板策略")
    print("=" * 80)
    create_all_weather_template()
