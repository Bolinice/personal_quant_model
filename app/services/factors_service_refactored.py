"""
因子服务重构示例
==================
展示如何使用Repository层重构Service层

重构前后对比:
- 重构前: Service直接依赖Session，包含数据访问逻辑
- 重构后: Service依赖Repository，只包含业务编排逻辑
"""

from datetime import date
from typing import List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.repositories.market_data_repo import MarketDataRepository
from app.repositories.factor_repo import FactorRepository
from app.core.factor_calculator import FactorCalculator
from app.core.factor_preprocess import FactorPreprocessor
from app.core.exceptions import BusinessException, InsufficientDataException


class FactorsServiceRefactored:
    """
    因子服务重构版

    职责:
    - 业务编排: 数据获取 → 因子计算 → 预处理 → 存储
    - 事务管理: 数据库事务边界
    - 异常处理: 业务异常转换
    """

    def __init__(self, session: Session):
        self.session = session
        # Repository层: 负责数据访问
        self.market_repo = MarketDataRepository(session)
        self.factor_repo = FactorRepository(session)
        # Core层: 负责纯计算
        self.calculator = FactorCalculator()
        self.preprocessor = FactorPreprocessor()

    def calc_and_save_factors(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
        factor_names: Optional[List[str]] = None,
    ) -> dict:
        """
        计算并保存因子

        业务流程:
        1. 从Repository获取市场数据
        2. 使用Core层计算因子
        3. 使用Core层预处理因子
        4. 通过Repository保存因子

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）
            factor_names: 因子名称列表（None表示全部）

        Returns:
            计算结果统计

        Raises:
            BusinessException: 业务异常
        """
        try:
            # Step 1: 获取数据（Repository层）
            price_df = self.market_repo.get_stock_daily(trade_date, ts_codes)
            financial_df = self.market_repo.get_financial_data_pit(trade_date, ts_codes)
            moneyflow_df = self.market_repo.get_money_flow(trade_date, ts_codes)

            # 数据验证
            if price_df.empty:
                raise InsufficientDataException(
                    message=f"{trade_date} 无日线数据",
                    context={"trade_date": str(trade_date)}
                )

            # Step 2: 计算因子（Core层 - 纯计算）
            factors_df = self.calculator.calc_factors(
                price_df=price_df,
                financial_df=financial_df,
                moneyflow_df=moneyflow_df,
                factor_names=factor_names,
            )

            # Step 3: 预处理因子（Core层 - 纯计算）
            factors_df = self.preprocessor.preprocess(
                factors_df,
                methods=["winsorize", "standardize", "neutralize"],
            )

            # Step 4: 保存因子（Repository层）
            saved_count = self.factor_repo.save_factors(factors_df)

            return {
                "trade_date": str(trade_date),
                "stocks_count": len(price_df),
                "factors_count": len(factors_df.columns),
                "saved_count": saved_count,
            }

        except InsufficientDataException:
            raise
        except Exception as e:
            raise BusinessException(
                message=f"计算因子失败: {trade_date}",
                context={"trade_date": str(trade_date), "error": str(e)}
            ) from e

    def get_factors(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
        factor_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取因子数据

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）
            factor_names: 因子名称列表（None表示全部）

        Returns:
            因子数据DataFrame

        Raises:
            BusinessException: 业务异常
        """
        try:
            # 直接委托给Repository层
            return self.factor_repo.get_factors(trade_date, ts_codes, factor_names)

        except Exception as e:
            raise BusinessException(
                message=f"获取因子数据失败: {trade_date}",
                context={"trade_date": str(trade_date), "error": str(e)}
            ) from e


# ==================== 重构前后对比 ====================

"""
重构前 (错误示例):
-------------------

class FactorsServiceOld:
    def __init__(self, session: Session):
        self.session = session
        self.calculator = FactorCalculator()

    def calc_and_save_factors(self, trade_date: date):
        # ❌ Service层直接查询数据库
        price_data = self.session.query(StockDaily).filter(
            StockDaily.trade_date == trade_date
        ).all()

        # ❌ ORM对象转DataFrame，效率低
        price_df = pd.DataFrame([{
            'ts_code': d.ts_code,
            'close': d.close,
            ...
        } for d in price_data])

        # ✅ 计算因子（这部分是对的）
        factors_df = self.calculator.calc_factors(price_df)

        # ❌ Service层直接插入数据库
        for _, row in factors_df.iterrows():
            factor = Factor(**row.to_dict())
            self.session.add(factor)
        self.session.commit()


重构后 (正确示例):
-------------------

class FactorsServiceRefactored:
    def __init__(self, session: Session):
        self.session = session
        self.market_repo = MarketDataRepository(session)  # ✅ 使用Repository
        self.factor_repo = FactorRepository(session)      # ✅ 使用Repository
        self.calculator = FactorCalculator()

    def calc_and_save_factors(self, trade_date: date):
        # ✅ Repository层查询，直接返回DataFrame
        price_df = self.market_repo.get_stock_daily(trade_date)

        # ✅ Core层纯计算
        factors_df = self.calculator.calc_factors(price_df)

        # ✅ Repository层批量保存
        self.factor_repo.save_factors(factors_df)


优势对比:
---------

1. 职责清晰:
   - Service层: 业务编排
   - Repository层: 数据访问
   - Core层: 纯计算

2. 易于测试:
   - Core层可独立测试（无需数据库）
   - Service层可Mock Repository测试
   - Repository层可单独测试数据访问

3. 性能优化:
   - Repository层使用pd.read_sql，避免ORM开销
   - 批量操作，避免N+1查询
   - 统一缓存策略

4. 代码复用:
   - Core层可在CLI、Jupyter Notebook中复用
   - Repository层可在多个Service中复用
"""
