"""
初始化预设策略
创建几个经典的多因子选股策略作为示例
"""

from app.db.base import SessionLocal
from app.models.models import Model, ModelFactorWeight

# 预设策略配置
PRESET_STRATEGIES = [
    {
        "model_code": "STR_PRESET_001",
        "model_name": "价值成长均衡策略",
        "model_type": "scoring",
        "description": "结合价值因子和成长因子，追求稳健收益。适合中长期持有，风险适中。",
        "version": "1.0",
        "status": "active",
        "is_default": True,
        "factor_weights": {
            "1": 0.15,   # ROE - 净资产收益率
            "5": 0.20,   # PE_TTM - 市盈率
            "6": 0.20,   # PB - 市净率
            "11": 0.25,  # REVENUE_GROWTH - 营收增长率
            "12": 0.20,  # PROFIT_GROWTH - 净利润增长率
        },
        "model_config": {
            "rebalance_freq": "monthly",
            "stock_count": 30,
            "industry_neutral": True,
        },
        "ic_mean": 0.045,
        "ic_ir": 1.2,
    },
    {
        "model_code": "STR_PRESET_002",
        "model_name": "动量反转策略",
        "model_type": "scoring",
        "description": "基于价格动量和成交量，捕捉短期趋势。适合波段操作，风险较高。",
        "version": "1.0",
        "status": "active",
        "is_default": True,
        "factor_weights": {
            "8": 0.30,   # MOM_20D - 20日动量
            "9": 0.35,   # MOM_60D - 60日动量
            "15": 0.20,  # TURNOVER_20D - 20日换手率
            "16": 0.15,  # AMOUNT_20D - 20日成交额
        },
        "model_config": {
            "rebalance_freq": "weekly",
            "stock_count": 20,
            "industry_neutral": False,
        },
        "ic_mean": 0.038,
        "ic_ir": 0.95,
    },
    {
        "model_code": "STR_PRESET_003",
        "model_name": "质量优选策略",
        "model_type": "scoring",
        "description": "专注高质量公司，强调盈利能力和财务稳健性。适合长期投资，风险较低。",
        "version": "1.0",
        "status": "active",
        "is_default": True,
        "factor_weights": {
            "1": 0.30,   # ROE - 净资产收益率
            "2": 0.20,   # ROA - 总资产收益率
            "3": 0.25,   # GROSS_MARGIN - 毛利率
            "4": 0.25,   # NET_MARGIN - 净利率
        },
        "model_config": {
            "rebalance_freq": "quarterly",
            "stock_count": 40,
            "industry_neutral": True,
        },
        "ic_mean": 0.052,
        "ic_ir": 1.45,
    },
    {
        "model_code": "STR_PRESET_004",
        "model_name": "低波红利策略",
        "model_type": "scoring",
        "description": "选择低波动、高分红的稳健标的。适合防御性配置，风险最低。",
        "version": "1.0",
        "status": "active",
        "is_default": True,
        "factor_weights": {
            "1": 0.25,   # ROE - 净资产收益率
            "6": 0.30,   # PB - 市净率（低估值）
            "13": 0.25,  # VOL_20D - 20日波动率（低波动）
            "14": 0.20,  # VOL_60D - 60日波动率（低波动）
        },
        "model_config": {
            "rebalance_freq": "quarterly",
            "stock_count": 50,
            "industry_neutral": True,
        },
        "ic_mean": 0.041,
        "ic_ir": 1.15,
    },
    {
        "model_code": "STR_PRESET_005",
        "model_name": "全能型多因子策略",
        "model_type": "scoring",
        "description": "综合价值、成长、质量、动量多个维度，全面评估股票。适合各类市场环境。",
        "version": "1.0",
        "status": "active",
        "is_default": True,
        "factor_weights": {
            "1": 0.12,   # ROE - 质量
            "3": 0.10,   # GROSS_MARGIN - 质量
            "5": 0.15,   # PE_TTM - 价值
            "6": 0.15,   # PB - 价值
            "9": 0.18,   # MOM_60D - 动量
            "11": 0.15,  # REVENUE_GROWTH - 成长
            "12": 0.15,  # PROFIT_GROWTH - 成长
        },
        "model_config": {
            "rebalance_freq": "monthly",
            "stock_count": 30,
            "industry_neutral": True,
        },
        "ic_mean": 0.048,
        "ic_ir": 1.28,
    },
]


def init_preset_strategies():
    """初始化预设策略"""
    db = SessionLocal()

    try:
        # 检查是否已存在预设策略
        existing_codes = {s.model_code for s in db.query(Model.model_code).filter(Model.is_default == True).all()}

        created_count = 0
        skipped_count = 0

        for strategy_config in PRESET_STRATEGIES:
            model_code = strategy_config["model_code"]

            # 跳过已存在的策略
            if model_code in existing_codes:
                print(f"⏭️  跳过已存在的策略: {model_code} - {strategy_config['model_name']}")
                skipped_count += 1
                continue

            # 构建因子ID列表
            factor_ids = [int(fid) for fid in strategy_config["factor_weights"].keys()]

            # 创建策略
            model = Model(
                model_code=model_code,
                model_name=strategy_config["model_name"],
                model_type=strategy_config["model_type"],
                description=strategy_config["description"],
                version=strategy_config["version"],
                status=strategy_config["status"],
                is_default=strategy_config["is_default"],
                factor_ids=factor_ids,
                factor_weights=strategy_config["factor_weights"],
                model_config=strategy_config["model_config"],
                ic_mean=strategy_config.get("ic_mean"),
                ic_ir=strategy_config.get("ic_ir"),
            )
            db.add(model)
            db.flush()  # 获取model.id

            # 创建因子权重关联
            for factor_id_str, weight in strategy_config["factor_weights"].items():
                fw = ModelFactorWeight(
                    model_id=model.id,
                    factor_id=int(factor_id_str),
                    weight=float(weight),
                )
                db.add(fw)

            db.commit()
            print(f"✅ 创建策略: {model_code} - {strategy_config['model_name']}")
            created_count += 1

        print(f"\n{'='*60}")
        print(f"预设策略初始化完成！")
        print(f"  ✅ 新创建: {created_count} 个")
        print(f"  ⏭️  跳过: {skipped_count} 个")
        print(f"  📊 总计: {created_count + skipped_count} 个预设策略")
        print(f"{'='*60}")

    except Exception as e:
        db.rollback()
        print(f"❌ 错误: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_preset_strategies()
