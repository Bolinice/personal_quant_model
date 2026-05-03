"""
运行模板策略回测并保存到数据库
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.backtests import Backtest, BacktestResult
from app.models.models import Model

# 模板策略配置
TEMPLATE_STRATEGIES = [
    {
        "model_name": "价值成长组合",
        "model_code": "TEMPLATE_VALUE_GROWTH",
        "description": "结合估值和成长因子，寻找价值被低估且具有成长潜力的股票",
        "factor_groups": ["valuation", "growth"],
        "top_n": 30,
        "backtest_file": "backtest_result_hs300_2024-01-01_2024-12-31.json",
    },
    {
        "model_name": "动量质量组合",
        "model_code": "TEMPLATE_MOMENTUM_QUALITY",
        "description": "结合动量和质量因子，选择趋势向上且基本面优质的股票",
        "factor_groups": ["momentum", "quality"],
        "top_n": 20,
        "backtest_file": "backtest_result_hs300_2024-01-01_2024-12-31.json",
    },
    {
        "model_name": "低波红利组合",
        "model_code": "TEMPLATE_LOW_VOL_DIVIDEND",
        "description": "结合低波动率和估值因子，构建防御性投资组合",
        "factor_groups": ["volatility", "valuation"],
        "top_n": 25,
        "backtest_file": "backtest_result_hs300_2024-01-01_2024-12-31.json",
    },
]


def load_backtest_result(file_path: str) -> dict:
    """加载回测结果文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_to_database():
    """将模板策略和回测结果保存到数据库"""
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        for i, strategy in enumerate(TEMPLATE_STRATEGIES, 1):
            print(f"\n[{i}/{len(TEMPLATE_STRATEGIES)}] 处理策略: {strategy['model_name']}")

            # 1. 检查模型是否已存在
            model = session.query(Model).filter_by(model_code=strategy["model_code"]).first()

            if not model:
                # 创建模型记录
                model = Model(
                    model_name=strategy["model_name"],
                    model_code=strategy["model_code"],
                    model_type="scoring",
                    description=strategy["description"],
                    version="1.0",
                    status="active",
                    model_config={
                        "factor_groups": strategy["factor_groups"],
                        "weighting_method": "equal_weight",
                        "neutralize_industry": True,
                        "neutralize_market_cap": True,
                        "is_template": True,
                        "top_n": strategy["top_n"],
                    },
                    is_default=True,  # 标记为默认模板
                    created_by=None,  # 系统模板
                )
                session.add(model)
                session.flush()
                print(f"  ✓ 创建模型记录 (ID: {model.id})")
            else:
                print(f"  ✓ 模型已存在 (ID: {model.id})")

            # 2. 加载回测结果
            backtest_file = project_root / strategy["backtest_file"]
            if not backtest_file.exists():
                print(f"  ✗ 回测结果文件不存在: {backtest_file}")
                continue

            result_data = load_backtest_result(str(backtest_file))
            print(f"  ✓ 加载回测结果")

            # 3. 检查回测记录是否已存在
            backtest = (
                session.query(Backtest)
                .filter_by(
                    model_id=model.id,
                    start_date=datetime.strptime(result_data["config"]["start_date"], "%Y-%m-%d").date(),
                    end_date=datetime.strptime(result_data["config"]["end_date"], "%Y-%m-%d").date(),
                )
                .first()
            )

            if not backtest:
                # 创建回测记录
                backtest = Backtest(
                    model_id=model.id,
                    job_name=f"{strategy['model_name']}_2024",
                    benchmark_code="000300.SH",
                    start_date=datetime.strptime(result_data["config"]["start_date"], "%Y-%m-%d").date(),
                    end_date=datetime.strptime(result_data["config"]["end_date"], "%Y-%m-%d").date(),
                    initial_capital=result_data["config"]["initial_capital"],
                    rebalance_freq=result_data["config"]["rebalance_freq"],
                    holding_count=strategy["top_n"],
                    status="success",
                    created_by=None,  # 系统模板
                )
                session.add(backtest)
                session.flush()
                print(f"  ✓ 创建回测记录 (ID: {backtest.id})")
            else:
                print(f"  ✓ 回测记录已存在 (ID: {backtest.id})")

            # 4. 检查回测结果是否已存在
            backtest_result = session.query(BacktestResult).filter_by(backtest_id=backtest.id).first()

            if not backtest_result:
                # 创建回测结果记录
                metrics = result_data["metrics"]
                backtest_result = BacktestResult(
                    backtest_id=backtest.id,
                    total_return=metrics["total_return"],
                    annual_return=metrics["annual_return"],
                    benchmark_return=metrics["benchmark_return"],
                    excess_return=metrics["excess_return"],
                    max_drawdown=metrics["max_drawdown"],
                    volatility=metrics["annual_volatility"],
                    sharpe=metrics["sharpe_ratio"],
                    calmar=metrics["calmar_ratio"],
                    information_ratio=metrics["information_ratio"],
                    turnover_rate=metrics["turnover_rate"],
                    win_rate=metrics["win_rate"],
                    metrics_json=result_data["metrics"],
                )
                session.add(backtest_result)
                print(f"  ✓ 创建回测结果记录")
            else:
                print(f"  ✓ 回测结果已存在")

        # 提交所有更改
        session.commit()
        print("\n✓ 所有模板策略已保存到数据库")

    except Exception as e:
        session.rollback()
        print(f"\n✗ 保存失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 80)
    print("保存模板策略回测结果到数据库")
    print("=" * 80)
    save_to_database()
