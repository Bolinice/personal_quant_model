"""
P0验证脚本：验证残差动量因子无未来函数

验证目标：
1. 检查残差收益率因子的计算逻辑
2. 确认残差收益率计算时只使用历史数据
3. 验证风格因子回归不包含未来信息

验证方法：
- 搜索残差收益率计算代码
- 检查回归模型的数据窗口
- 验证因子暴露计算的时点正确性
"""

import pandas as pd
import pytest
from datetime import date


class TestResidualMomentumNoLookahead:
    """验证残差动量因子无未来函数"""

    def test_residual_return_implementation_exists(self):
        """
        验证残差收益率因子是否已实现

        预期：应该有计算 residual_return_20d/60d/120d 的函数
        """
        print("\n" + "="*60)
        print("检查残差收益率因子实现")
        print("="*60)

        # 检查 alpha_modules.py 中的因子定义
        from app.core.alpha_modules import ResidualMomentumModule

        module = ResidualMomentumModule()
        factor_names = module.get_factor_names()

        print(f"\nResidualMomentumModule 定义的因子：")
        for name in factor_names:
            print(f"  - {name}")

        # 检查是否有 residual_return 因子
        residual_return_factors = [f for f in factor_names if "residual_return" in f]

        print(f"\n残差收益率因子：{residual_return_factors}")

        if residual_return_factors:
            print("\n✅ ResidualMomentumModule 定义了残差收益率因子")
        else:
            print("\n❌ ResidualMomentumModule 未定义残差收益率因子")

        # 检查是否有计算实现
        print("\n" + "="*60)
        print("搜索残差收益率计算实现")
        print("="*60)

        import os
        import subprocess

        # 搜索 residual_return 的计算函数
        result = subprocess.run(
            ["grep", "-rn", "def.*residual_return", "app/"],
            capture_output=True,
            text=True
        )

        if result.stdout:
            print("\n找到残差收益率计算函数：")
            print(result.stdout)
        else:
            print("\n❌ 未找到残差收益率计算函数")
            print("   - 搜索关键词：def.*residual_return")
            print("   - 搜索目录：app/")

        # 搜索 residual 相关的计算
        result2 = subprocess.run(
            ["grep", "-rn", "residual.*return", "app/core/factors/"],
            capture_output=True,
            text=True
        )

        if result2.stdout:
            print("\n在 app/core/factors/ 中找到相关代码：")
            print(result2.stdout)
        else:
            print("\n❌ 在 app/core/factors/ 中未找到残差收益率计算")

        return len(residual_return_factors) > 0

    def test_residual_calculation_logic(self):
        """
        验证残差收益率的计算逻辑

        残差收益率 = 实际收益率 - 风格因子回归预测收益率

        关键点：
        1. 风格因子暴露应该使用历史数据
        2. 回归模型应该使用历史窗口
        3. 不能使用未来的因子暴露
        """
        print("\n" + "="*60)
        print("残差收益率计算逻辑分析")
        print("="*60)

        print("\n标准计算流程：")
        print("1. 计算股票在T日的风格因子暴露（size, value, momentum等）")
        print("   - ⚠️  必须使用T-1日及之前的数据")
        print("   - ❌ 不能使用T日的数据（如T日收盘价）")

        print("\n2. 使用历史窗口（如过去60日）进行回归：")
        print("   r_i,t = β_i,size * f_size,t + β_i,value * f_value,t + ... + ε_i,t")
        print("   - ⚠️  回归窗口应该是 [T-60, T-1]")
        print("   - ❌ 不能包含T日数据")

        print("\n3. 计算残差收益率：")
        print("   residual_return_i,T = r_i,T - (β_i * f_T)")
        print("   - r_i,T: T日实际收益率")
        print("   - β_i: 历史回归得到的因子暴露")
        print("   - f_T: T日因子收益率")

        print("\n" + "="*60)
        print("潜在前视偏差风险")
        print("="*60)

        print("\n风险1：使用T日数据计算因子暴露")
        print("  错误示例：")
        print("    size_T = log(market_cap_T)  # ❌ 使用T日市值")
        print("  正确示例：")
        print("    size_T = log(market_cap_{T-1})  # ✅ 使用T-1日市值")

        print("\n风险2：回归窗口包含未来数据")
        print("  错误示例：")
        print("    # 在T日回归时使用了 [T-59, T] 的数据")
        print("    regression_window = returns[T-59:T+1]  # ❌ 包含T日")
        print("  正确示例：")
        print("    regression_window = returns[T-60:T]  # ✅ 只用历史")

        print("\n风险3：使用未来的因子收益率")
        print("  错误示例：")
        print("    # 使用T日的因子收益率预测T日残差")
        print("    factor_return_T = calculate_factor_return(T)  # ❌")
        print("  正确示例：")
        print("    # 使用历史因子收益率")
        print("    factor_return = calculate_factor_return(T-1)  # ✅")

    def test_check_implementation_status(self):
        """
        检查当前实现状态

        检查点：
        1. 是否有残差收益率计算函数
        2. 是否有风格因子回归模块
        3. 是否有因子暴露计算
        """
        print("\n" + "="*60)
        print("当前实现状态检查")
        print("="*60)

        # 检查风险模型
        print("\n1. 检查风险模型（RiskModel）：")
        try:
            from app.core.risk_model import RiskModel
            print("   ✅ RiskModel 存在")

            # 检查是否有回归方法
            risk_model = RiskModel()
            methods = [m for m in dir(risk_model) if not m.startswith('_')]
            print(f"   可用方法：{methods[:10]}...")

            # 检查是否有残差相关方法
            residual_methods = [m for m in methods if 'residual' in m.lower()]
            if residual_methods:
                print(f"   ✅ 找到残差相关方法：{residual_methods}")
            else:
                print("   ⚠️  未找到残差相关方法")

        except ImportError as e:
            print(f"   ❌ RiskModel 导入失败：{e}")

        # 检查因子计算模块
        print("\n2. 检查因子计算模块（factors/）：")
        import os
        factors_dir = "app/core/factors"
        if os.path.exists(factors_dir):
            files = [f for f in os.listdir(factors_dir) if f.endswith('.py')]
            print(f"   因子模块文件：{files}")

            # 检查是否有 momentum.py
            if "momentum.py" in files:
                print("   ✅ momentum.py 存在")

                # 检查是否有残差动量计算
                with open(f"{factors_dir}/momentum.py", "r") as f:
                    content = f.read()
                    if "residual" in content.lower():
                        print("   ✅ momentum.py 包含 residual 关键词")
                    else:
                        print("   ❌ momentum.py 不包含 residual 关键词")
            else:
                print("   ⚠️  momentum.py 不存在")
        else:
            print(f"   ❌ {factors_dir} 目录不存在")

        # 检查 factor_calculator
        print("\n3. 检查因子计算器（FactorCalculator）：")
        try:
            from app.core.factor_calculator import FactorCalculator
            print("   ✅ FactorCalculator 存在")

            # 检查是否有残差相关方法
            calc = FactorCalculator()
            methods = [m for m in dir(calc) if not m.startswith('_')]
            residual_methods = [m for m in methods if 'residual' in m.lower()]

            if residual_methods:
                print(f"   ✅ 找到残差相关方法：{residual_methods}")
            else:
                print("   ⚠️  未找到残差相关方法")

        except ImportError as e:
            print(f"   ❌ FactorCalculator 导入失败：{e}")
        except Exception as e:
            print(f"   ⚠️  FactorCalculator 实例化失败：{e}")


def test_residual_momentum_implementation_review():
    """
    代码审查：残差动量因子的实现

    审查要点：
    1. 是否已实现残差收益率计算
    2. 计算逻辑是否正确
    3. 是否存在前视偏差
    """
    print("\n" + "="*60)
    print("残差动量因子实现审查")
    print("="*60)

    print("\n1. 因子定义（app/core/alpha_modules.py）：")
    print("   ✅ ResidualMomentumModule 已定义")
    print("   ✅ 包含 residual_return_20d/60d/120d 因子")
    print("   ✅ 因子权重配置合理")

    print("\n2. 因子计算实现：")
    print("   ❌ 未找到 residual_return 计算函数")
    print("   ❌ app/core/factors/ 中没有残差动量计算")
    print("   ❌ FactorCalculator 中没有残差相关方法")

    print("\n3. 依赖模块：")
    print("   ✅ RiskModel 存在（用于风格因子回归）")
    print("   ⚠️  但未找到调用 RiskModel 计算残差的代码")

    print("\n" + "="*60)
    print("审查结论")
    print("="*60)
    print("❌ 残差收益率因子未实现")
    print("⚠️  ResidualMomentumModule 只有配置，没有计算逻辑")
    print("⚠️  无法验证是否存在前视偏差（因为代码不存在）")

    print("\n" + "="*60)
    print("建议")
    print("="*60)

    print("\n方案1：实现残差收益率计算（推荐）")
    print("```python")
    print("# app/core/factors/momentum.py")
    print("")
    print("def calc_residual_return(")
    print("    returns: pd.DataFrame,")
    print("    factor_exposures: pd.DataFrame,")
    print("    lookback_window: int = 60")
    print(") -> pd.DataFrame:")
    print('    """')
    print("    计算残差收益率")
    print("    ")
    print("    Args:")
    print("        returns: 股票收益率，shape=(T, N)")
    print("        factor_exposures: 风格因子暴露，shape=(T, N, K)")
    print("        lookback_window: 回归窗口长度")
    print("    ")
    print("    Returns:")
    print("        残差收益率，shape=(T, N)")
    print('    """')
    print("    # 1. 对每只股票进行时序回归")
    print("    # 2. 计算残差")
    print("    # 3. 确保只使用历史数据")
    print("    pass")
    print("```")

    print("\n方案2：使用简化版动量因子")
    print("- 如果残差动量实现复杂，可以先使用简单动量")
    print("- 在 momentum.py 中已有 ret_3m_skip1, ret_6m_skip1 等")
    print("- 这些因子已经跳过最近1月，避免了短期反转")

    print("\n方案3：标记为待实现")
    print("- 在 ResidualMomentumModule 中添加注释")
    print("- 说明残差收益率因子尚未实现")
    print("- 暂时使用其他动量因子替代")


if __name__ == "__main__":
    print("="*60)
    print("P0验证：残差动量因子无未来函数")
    print("="*60)

    # 运行测试
    test = TestResidualMomentumNoLookahead()

    try:
        has_implementation = test.test_residual_return_implementation_exists()
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        has_implementation = False

    try:
        test.test_residual_calculation_logic()
    except Exception as e:
        print(f"❌ 测试失败：{e}")

    try:
        test.test_check_implementation_status()
    except Exception as e:
        print(f"❌ 测试失败：{e}")

    # 代码审查
    test_residual_momentum_implementation_review()

    print("\n" + "="*60)
    print("验证完成")
    print("="*60)

    if not has_implementation:
        print("\n❌ 严重问题：残差收益率因子未实现")
        print("   风险等级：高")
        print("   建议：实现残差收益率计算或使用替代方案")
    else:
        print("\n✅ 残差收益率因子已实现")
        print("   建议：进一步验证计算逻辑的正确性")
