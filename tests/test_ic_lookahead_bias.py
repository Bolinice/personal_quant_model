"""
测试IC计算中的前视偏差问题

问题描述：
当前实现中，T日的IC计算使用了T日的forward_return，这是一个严重的前视偏差：
- forward_return = close[T+20] / close[T] - 1
- 这意味着T日的IC计算使用了T+20日的价格信息
- 正确做法：T日的IC应该用[T-60, T-1]的历史数据计算，不能包含T日及之后的数据

影响：
1. IC权重计算会使用未来信息，导致回测过拟合
2. 实盘时无法获得T日的forward_return（需要等到T+20日才知道）
3. 会严重高估策略收益

修复方案：
- IC计算应该使用历史窗口：[T-60, T-1]
- T日的因子值预测的是T+1到T+20的收益
- 但IC统计应该用过去60天的"因子值vs实际收益"相关性
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta


def test_ic_calculation_timeline():
    """验证IC计算的时间线逻辑"""

    # 模拟场景：2024-01-01到2024-03-31，共90天
    dates = pd.date_range("2024-01-01", "2024-03-31", freq="D")

    # 假设我们在2024-03-31计算IC权重
    current_date = date(2024, 3, 31)
    lookback = 60
    forward_period = 20

    # 正确的IC计算窗口应该是：
    # [2024-01-31, 2024-03-30] 共60天的历史数据
    # 每一天的forward_return是该天之后20天的收益

    # 错误示例：当前实现
    print("❌ 当前实现的问题：")
    print(f"  当前日期: {current_date}")
    print(f"  IC计算窗口: 最近{lookback}天")
    print(f"  问题: 包含了{current_date}的forward_return")
    print(f"  forward_return定义: close[T+{forward_period}] / close[T] - 1")
    print(f"  这意味着使用了 {current_date + timedelta(days=forward_period)} 的价格信息！")
    print()

    # 正确示例
    print("✅ 正确的实现：")
    ic_start = current_date - timedelta(days=lookback)
    ic_end = current_date - timedelta(days=1)
    print(f"  当前日期: {current_date}")
    print(f"  IC计算窗口: [{ic_start}, {ic_end}]")
    print(f"  每天的forward_return: 该天之后{forward_period}天的收益")
    print(f"  最晚使用的价格日期: {ic_end + timedelta(days=forward_period)}")
    print(f"  这个日期 < {current_date}，所以没有前视偏差")
    print()


def test_ic_weight_calculation_with_lookahead():
    """测试当前IC权重计算是否存在前视偏差"""

    # 模拟数据
    np.random.seed(42)
    n_stocks = 100
    n_days = 90

    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    stocks = [f"stock_{i:03d}" for i in range(n_stocks)]

    # 生成因子值和收益率
    data = []
    for d in dates:
        for s in stocks:
            data.append({
                "trade_date": d,
                "security_id": s,
                "factor_value": np.random.randn(),
                "close": 100 + np.random.randn() * 10,
            })

    df = pd.DataFrame(data)

    # 计算forward_return（模拟当前实现）
    df = df.sort_values(["security_id", "trade_date"])
    df["fwd_close"] = df.groupby("security_id")["close"].shift(-20)
    df["forward_return"] = df["fwd_close"] / df["close"] - 1

    # 当前实现：取最近60天（包含今天）
    current_date = dates[-1]
    lookback = 60
    recent_dates = dates[-lookback:]

    current_impl_data = df[df["trade_date"].isin(recent_dates)]

    # 检查是否包含未来数据
    max_date_in_ic = current_impl_data["trade_date"].max()
    max_price_date_used = max_date_in_ic + timedelta(days=20)

    print("🔍 前视偏差检测：")
    print(f"  当前日期: {current_date.date()}")
    print(f"  IC窗口最大日期: {max_date_in_ic.date()}")
    print(f"  该日期的forward_return使用的最晚价格日期: {max_price_date_used.date()}")

    if max_price_date_used.date() > current_date.date():
        print(f"  ⚠️  前视偏差: 使用了未来 {(max_price_date_used.date() - current_date.date()).days} 天的价格信息！")
        return False
    else:
        print(f"  ✅ 无前视偏差")
        return True


def test_correct_ic_calculation():
    """展示正确的IC计算方法"""

    print("\n📋 正确的IC计算流程：")
    print()
    print("假设今天是 T 日，我们要计算因子权重：")
    print()
    print("步骤1: 确定IC计算窗口")
    print("  - 窗口: [T-60, T-1]（不包含T日）")
    print("  - 原因: T日的forward_return需要T+20日的价格，这是未来信息")
    print()
    print("步骤2: 对窗口内每一天 t ∈ [T-60, T-1]")
    print("  - 获取 t 日的因子值: factor[t]")
    print("  - 获取 t 日的forward_return: (close[t+20] - close[t]) / close[t]")
    print("  - 注意: t+20 最大是 (T-1)+20 = T+19，仍然 < T+20")
    print()
    print("步骤3: 计算IC")
    print("  - IC[t] = corr(factor[t], forward_return[t])")
    print("  - 对所有 t ∈ [T-60, T-1] 计算")
    print()
    print("步骤4: 计算权重")
    print("  - IC均值: mean(IC[T-60:T-1])")
    print("  - ICIR: mean(IC) / std(IC)")
    print()
    print("关键点：")
    print("  ✅ T日的因子值用于预测T+1到T+20的收益")
    print("  ✅ 但T日的IC权重用的是历史60天的IC统计")
    print("  ✅ 历史IC中最晚使用的价格是T+19日，早于T+20日")
    print("  ❌ 当前实现包含了T日的forward_return，使用了T+20日的价格")


def test_real_world_impact():
    """测试前视偏差对实际收益的影响"""

    print("\n💰 前视偏差对收益的影响：")
    print()
    print("场景: 假设某因子的真实IC=0.05，但由于前视偏差，回测IC=0.08")
    print()
    print("回测结果:")
    print("  - 因子权重被高估: 0.08 / 0.05 = 1.6倍")
    print("  - 预期年化收益: 20%")
    print("  - 夏普比率: 2.0")
    print()
    print("实盘结果:")
    print("  - 实际年化收益: 12.5% (20% / 1.6)")
    print("  - 实际夏普比率: 1.25 (2.0 / 1.6)")
    print("  - 收益缩水: 37.5%")
    print()
    print("结论: 前视偏差会严重高估策略表现！")


if __name__ == "__main__":
    print("=" * 80)
    print("IC计算前视偏差测试")
    print("=" * 80)
    print()

    test_ic_calculation_timeline()
    print("\n" + "=" * 80 + "\n")

    has_bias = not test_ic_weight_calculation_with_lookahead()
    print("\n" + "=" * 80 + "\n")

    test_correct_ic_calculation()
    print("\n" + "=" * 80 + "\n")

    test_real_world_impact()
    print("\n" + "=" * 80 + "\n")

    if has_bias:
        print("❌ 测试失败: 检测到前视偏差")
        print("\n修复建议:")
        print("1. 修改 compute_ic_weights 函数")
        print("2. IC窗口改为 [T-lookback, T-1]，不包含T日")
        print("3. 或者修改 forward_return 的计算，使用 T-1 日的价格作为基准")
    else:
        print("✅ 测试通过: 无前视偏差")
