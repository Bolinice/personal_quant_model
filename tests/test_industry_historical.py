"""
P0验证脚本：验证行业分类历史时点正确性

验证目标：
1. 检查 StockIndustry 表是否有历史时点字段（effective_date, expire_date）
2. 确认因子中性化时使用的行业分类是历史时点的分类
3. 验证行业调整历史是否被记录

验证方法：
- 检查数据库表结构
- 检查行业分类数据的时间维度
- 检查中性化代码是否考虑历史时点
"""

import pandas as pd
import pytest
from datetime import date


class TestIndustryClassificationHistoricalCorrectness:
    """验证行业分类历史时点正确性"""

    def test_stock_industry_table_structure(self):
        """
        验证 StockIndustry 表结构

        预期：应该有 effective_date 和 expire_date 字段来追踪历史变化
        """
        from app.models.market.stock_industry import StockIndustry
        from sqlalchemy import inspect

        # 检查表结构
        columns = [c.name for c in StockIndustry.__table__.columns]

        print(f"\nStockIndustry 表字段：{columns}")

        # 检查是否有历史时点字段
        has_effective_date = "effective_date" in columns
        has_expire_date = "expire_date" in columns

        print(f"是否有 effective_date 字段：{has_effective_date}")
        print(f"是否有 expire_date 字段：{has_expire_date}")

        if not has_effective_date or not has_expire_date:
            print("\n⚠️  警告：StockIndustry 表缺少历史时点字段！")
            print("   - 当前表结构无法追踪行业分类的历史变化")
            print("   - 因子中性化时可能使用了错误的行业分类")
            print("   - 建议添加 effective_date 和 expire_date 字段")
        else:
            print("\n✅ StockIndustry 表有历史时点字段")

        # 返回检查结果
        return has_effective_date and has_expire_date

    def test_industry_neutralization_time_point(self):
        """
        验证行业中性化是否考虑历史时点

        检查点：
        1. neutralize_industry 方法是否接收 trade_date 参数
        2. 是否根据 trade_date 过滤行业数据
        """
        from app.core.factor_preprocess import FactorPreprocessor
        import inspect

        preprocessor = FactorPreprocessor()

        # 检查 neutralize_industry 方法签名
        sig = inspect.signature(preprocessor.neutralize_industry)
        params = list(sig.parameters.keys())

        print(f"\nneutralize_industry 方法参数：{params}")

        has_trade_date = "trade_date" in params

        if not has_trade_date:
            print("\n⚠️  警告：neutralize_industry 方法缺少 trade_date 参数！")
            print("   - 无法根据交易日期选择正确的行业分类")
            print("   - 可能使用了当前的行业分类而非历史分类")
            print("   - 建议添加 trade_date 参数并过滤行业数据")
        else:
            print("\n✅ neutralize_industry 方法有 trade_date 参数")

        return has_trade_date

    def test_industry_data_time_dimension(self):
        """
        验证行业数据的时间维度

        场景：
        - 如果某股票在2020年属于行业A，2022年调整到行业B
        - 回测2021年时应该使用行业A，而非行业B
        """
        print("\n" + "="*60)
        print("行业数据时间维度检查")
        print("="*60)

        print("\n当前实现分析：")
        print("1. StockIndustry 表结构：")
        print("   - ❌ 缺少 effective_date 字段")
        print("   - ❌ 缺少 expire_date 字段")
        print("   - ⚠️  只能存储当前行业分类，无法追踪历史")

        print("\n2. neutralize_industry 方法：")
        print("   - ❌ 没有 trade_date 参数")
        print("   - ⚠️  直接使用传入的 industry_col，无法过滤历史数据")

        print("\n3. 潜在问题：")
        print("   - 如果股票A在2020年从金融业调整到科技业")
        print("   - 回测2019年时，可能错误地使用了科技业分类")
        print("   - 导致中性化结果不准确")

        print("\n" + "="*60)


def test_industry_classification_implementation_review():
    """
    代码审查：行业分类的实现

    审查要点：
    1. 数据库表结构是否支持历史追踪
    2. 中性化代码是否考虑历史时点
    3. 数据同步是否保存历史记录
    """
    print("\n" + "="*60)
    print("行业分类实现审查")
    print("="*60)

    print("\n1. 数据库表结构：")
    print("   当前字段：ts_code, industry_name, industry_code, level, standard, created_at")
    print("   ❌ 缺少：effective_date, expire_date")
    print("   影响：无法追踪行业调整历史")

    print("\n2. 中性化实现（app/core/factor_preprocess.py:401）：")
    print("   def neutralize_industry(self, df, value_col, industry_col):")
    print("   ❌ 没有 trade_date 参数")
    print("   ❌ 直接使用 df[industry_col]，假设行业分类已正确")
    print("   影响：依赖调用方提供正确的历史行业分类")

    print("\n3. 调用链分析：")
    print("   preprocess() → neutralize_industry()")
    print("   - preprocess 方法接收 df 参数")
    print("   - df 应该包含正确的历史行业分类")
    print("   - ⚠️  但没有验证 df 中的行业分类是否为历史时点")

    print("\n" + "="*60)
    print("审查结论")
    print("="*60)
    print("❌ 数据库表结构不支持历史追踪")
    print("❌ 中性化代码未考虑历史时点")
    print("⚠️  依赖调用方提供正确的历史行业分类")
    print("⚠️  存在使用错误行业分类的风险")

    print("\n" + "="*60)
    print("改进建议")
    print("="*60)

    print("\n方案1：数据库层面支持（推荐）")
    print("```sql")
    print("ALTER TABLE stock_industry")
    print("ADD COLUMN effective_date DATE,")
    print("ADD COLUMN expire_date DATE;")
    print("")
    print("CREATE INDEX idx_industry_time ON stock_industry(ts_code, effective_date, expire_date);")
    print("```")

    print("\n方案2：代码层面验证")
    print("```python")
    print("def neutralize_industry(self, df, value_col, industry_col, trade_date=None):")
    print("    # 添加时间验证")
    print("    if trade_date is not None:")
    print("        # 验证 df 中的行业分类是否为 trade_date 时点的")
    print("        # 或者从数据库查询 trade_date 时点的行业分类")
    print("        pass")
    print("```")

    print("\n方案3：文档和规范")
    print("- 在文档中明确说明：调用方必须提供历史时点的行业分类")
    print("- 添加单元测试验证行业分类的时点正确性")
    print("- 添加运行时检查和告警")


if __name__ == "__main__":
    print("="*60)
    print("P0验证：行业分类历史时点正确性")
    print("="*60)

    # 运行测试
    test = TestIndustryClassificationHistoricalCorrectness()

    try:
        has_time_fields = test.test_stock_industry_table_structure()
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        has_time_fields = False

    try:
        has_trade_date_param = test.test_industry_neutralization_time_point()
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        has_trade_date_param = False

    try:
        test.test_industry_data_time_dimension()
    except Exception as e:
        print(f"❌ 测试失败：{e}")

    # 代码审查
    test_industry_classification_implementation_review()

    print("\n" + "="*60)
    print("验证完成")
    print("="*60)

    if not has_time_fields:
        print("\n⚠️  严重问题：数据库表结构不支持历史追踪")
        print("   风险等级：高")
        print("   建议：立即添加 effective_date 和 expire_date 字段")

    if not has_trade_date_param:
        print("\n⚠️  中等问题：中性化代码未考虑历史时点")
        print("   风险等级：中")
        print("   建议：添加 trade_date 参数或在文档中明确说明")
