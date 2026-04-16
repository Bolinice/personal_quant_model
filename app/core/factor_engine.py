"""
因子计算引擎
实现PRD中定义的各类因子计算逻辑
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.models.factors import Factor, FactorValue
from app.models.market import StockDaily, StockFinancial, StockBasic
from app.core.logging import logger


class FactorCalculator:
    """因子计算器基类"""

    def __init__(self, db: Session = None):
        self.db = db

    def get_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票日线数据"""
        query = self.db.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).order_by(StockDaily.trade_date)

        data = query.all()
        if not data:
            return pd.DataFrame()

        return pd.DataFrame([{
            'trade_date': d.trade_date,
            'open': float(d.open) if d.open else None,
            'high': float(d.high) if d.high else None,
            'low': float(d.low) if d.low else None,
            'close': float(d.close) if d.close else None,
            'volume': float(d.vol) if d.vol else None,
            'amount': float(d.amount) if d.amount else None,
            'pct_chg': float(d.pct_chg) if d.pct_chg else None,
        } for d in data])

    def get_financial_data(self, ts_code: str) -> Optional[Dict]:
        """获取财务数据"""
        financial = self.db.query(StockFinancial).filter(
            StockFinancial.ts_code == ts_code
        ).order_by(StockFinancial.end_date.desc()).first()

        if not financial:
            return None

        return {
            'revenue': float(financial.revenue) if financial.revenue else None,
            'net_profit': float(financial.net_profit) if financial.net_profit else None,
            'total_assets': float(financial.total_assets) if financial.total_assets else None,
            'total_equity': float(financial.total_equity) if financial.total_equity else None,
            'operating_cash_flow': float(financial.operating_cash_flow) if financial.operating_cash_flow else None,
            'gross_profit': float(financial.gross_profit) if financial.gross_profit else None,
        }


class QualityFactorCalculator(FactorCalculator):
    """质量因子计算器"""

    def calc_roe(self, ts_code: str) -> Optional[float]:
        """ROE = 净利润 / 净资产"""
        financial = self.get_financial_data(ts_code)
        if not financial or not financial.get('net_profit') or not financial.get('total_equity'):
            return None
        if financial['total_equity'] == 0:
            return None
        return financial['net_profit'] / financial['total_equity']

    def calc_roa(self, ts_code: str) -> Optional[float]:
        """ROA = 净利润 / 总资产"""
        financial = self.get_financial_data(ts_code)
        if not financial or not financial.get('net_profit') or not financial.get('total_assets'):
            return None
        if financial['total_assets'] == 0:
            return None
        return financial['net_profit'] / financial['total_assets']

    def calc_gross_margin(self, ts_code: str) -> Optional[float]:
        """毛利率 = 毛利 / 营收"""
        financial = self.get_financial_data(ts_code)
        if not financial or not financial.get('gross_profit') or not financial.get('revenue'):
            return None
        if financial['revenue'] == 0:
            return None
        return financial['gross_profit'] / financial['revenue']

    def calc_net_margin(self, ts_code: str) -> Optional[float]:
        """净利率 = 净利润 / 营收"""
        financial = self.get_financial_data(ts_code)
        if not financial or not financial.get('net_profit') or not financial.get('revenue'):
            return None
        if financial['revenue'] == 0:
            return None
        return financial['net_profit'] / financial['revenue']

    def calc_operating_cash_flow_ratio(self, ts_code: str) -> Optional[float]:
        """经营现金流/净利润"""
        financial = self.get_financial_data(ts_code)
        if not financial:
            return None
        net_profit = financial.get('net_profit')
        ocf = financial.get('operating_cash_flow')
        if not net_profit or net_profit == 0:
            return None
        return ocf / net_profit if ocf else None


class ValuationFactorCalculator(FactorCalculator):
    """估值因子计算器"""

    def calc_pe_ttm(self, ts_code: str, trade_date: str) -> Optional[float]:

        """PE(TTM) = 总市值 / 过去12个月净利润"""
        # 获取当日收盘价和总股本
        daily = self.db.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == trade_date
        ).first()

        if not daily:
            return None

        # 获取过去12个月净利润
        financial = self.db.query(StockFinancial).filter(
            StockFinancial.ts_code == ts_code,
            StockFinancial.end_date <= trade_date
        ).order_by(StockFinancial.end_date.desc()).first()

        if not financial or not financial.net_profit or float(financial.net_profit) <= 0:
            return None

        # 简化计算：使用当日市值
        amount = float(daily.amount) if daily.amount else 0
        vol = float(daily.vol) if daily.vol else 0
        if vol == 0:
            return None

        # 市值估算 = 成交额 / 换手率 (简化)
        net_profit = float(financial.net_profit)
        if net_profit == 0:
            return None

        return amount / (vol * net_profit / 1e8) if vol > 0 else None

    def calc_pb(self, ts_code: str, trade_date: str) -> Optional[float]:
        """PB = 总市值 / 净资产"""
        daily = self.db.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == trade_date
        ).first()

        if not daily:
            return None

        financial = self.db.query(StockFinancial).filter(
            StockFinancial.ts_code == ts_code,
            StockFinancial.end_date <= trade_date
        ).order_by(StockFinancial.end_date.desc()).first()

        if not financial or not financial.total_equity or float(financial.total_equity) <= 0:
            return None

        close = float(daily.close) if daily.close else 0
        equity = float(financial.total_equity)

        # 简化：PB = 股价 / 每股净资产
        # 需要总股本数据，这里用简化估算
        return close / (equity / 1e8)  # 假设总股本约1亿股

    def calc_ps_ttm(self, ts_code: str, trade_date: str) -> Optional[float]:
        """PS(TTM) = 总市值 / 过去12个月营收"""
        daily = self.db.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == trade_date
        ).first()

        if not daily:
            return None

        financial = self.db.query(StockFinancial).filter(
            StockFinancial.ts_code == ts_code,
            StockFinancial.end_date <= trade_date
        ).order_by(StockFinancial.end_date.desc()).first()

        if not financial or not financial.revenue or float(financial.revenue) <= 0:
            return None

        close = float(daily.close) if daily.close else 0
        revenue = float(financial.revenue)

        return close / (revenue / 1e8)  # 简化估算


class MomentumFactorCalculator(FactorCalculator):
    """动量因子计算器"""

    def calc_momentum(self, ts_code: str, trade_date: str, period: int = 20) -> Optional[float]:
        """
        计算动量因子（收益率）
        period: 回看天数
        """
        end_date = datetime.strptime(trade_date, "%Y-%m-%d")
        start_date = (end_date - timedelta(days=period * 2)).strftime("%Y-%m-%d")  # 多取一些数据

        df = self.get_stock_daily(ts_code, start_date, trade_date)
        if df.empty or len(df) < period:
            return None

        # 计算收益率
        df = df.sort_values('trade_date')
        close = df['close'].values

        if len(close) < period + 1:
            return None

        return close[-1] / close[-period - 1] - 1

    def calc_momentum_20d(self, ts_code: str, trade_date: str) -> Optional[float]:
        """20日动量"""
        return self.calc_momentum(ts_code, trade_date, 20)

    def calc_momentum_60d(self, ts_code: str, trade_date: str) -> Optional[float]:
        """60日动量"""
        return self.calc_momentum(ts_code, trade_date, 60)

    def calc_momentum_120d(self, ts_code: str, trade_date: str) -> Optional[float]:
        """120日动量"""
        return self.calc_momentum(ts_code, trade_date, 120)


class GrowthFactorCalculator(FactorCalculator):
    """成长因子计算器"""

    def calc_revenue_growth(self, ts_code: str) -> Optional[float]:
        """营收同比增长率"""
        financials = self.db.query(StockFinancial).filter(
            StockFinancial.ts_code == ts_code
        ).order_by(StockFinancial.end_date.desc()).limit(2).all()

        if len(financials) < 2:
            return None

        current = float(financials[0].revenue) if financials[0].revenue else None
        previous = float(financials[1].revenue) if financials[1].revenue else None

        if not current or not previous or previous == 0:
            return None

        return (current - previous) / previous

    def calc_profit_growth(self, ts_code: str) -> Optional[float]:
        """净利润同比增长率"""
        financials = self.db.query(StockFinancial).filter(
            StockFinancial.ts_code == ts_code
        ).order_by(StockFinancial.end_date.desc()).limit(2).all()

        if len(financials) < 2:
            return None

        current = float(financials[0].net_profit) if financials[0].net_profit else None
        previous = float(financials[1].net_profit) if financials[1].net_profit else None

        if not current or not previous or previous == 0:
            return None

        return (current - previous) / previous


class RiskFactorCalculator(FactorCalculator):
    """风险因子计算器"""

    def calc_volatility(self, ts_code: str, trade_date: str, period: int = 20) -> Optional[float]:
        """
        计算年化波动率
        period: 回看天数
        """
        end_date = datetime.strptime(trade_date, "%Y-%m-%d")
        start_date = (end_date - timedelta(days=period * 2)).strftime("%Y-%m-%d")

        df = self.get_stock_daily(ts_code, start_date, trade_date)
        if df.empty or len(df) < period:
            return None

        # 计算日收益率
        df = df.sort_values('trade_date')
        returns = df['pct_chg'].values[-period:] / 100  # 转换为小数

        # 年化波动率 = std * sqrt(252)
        return np.std(returns) * np.sqrt(252)

    def calc_volatility_20d(self, ts_code: str, trade_date: str) -> Optional[float]:
        """20日波动率"""
        return self.calc_volatility(ts_code, trade_date, 20)

    def calc_volatility_60d(self, ts_code: str, trade_date: str) -> Optional[float]:
        """60日波动率"""
        return self.calc_volatility(ts_code, trade_date, 60)

    def calc_downside_volatility(self, ts_code: str, trade_date: str, period: int = 60) -> Optional[float]:
        """下行波动率"""
        end_date = datetime.strptime(trade_date, "%Y-%m-%d")
        start_date = (end_date - timedelta(days=period * 2)).strftime("%Y-%m-%d")

        df = self.get_stock_daily(ts_code, start_date, trade_date)
        if df.empty or len(df) < period:
            return None

        df = df.sort_values('trade_date')
        returns = df['pct_chg'].values[-period:] / 100

        # 只计算负收益
        negative_returns = returns[returns < 0]

        if len(negative_returns) == 0:
            return 0.0

        return np.std(negative_returns) * np.sqrt(252)


class LiquidityFactorCalculator(FactorCalculator):
    """流动性因子计算器"""

    def calc_avg_amount(self, ts_code: str, trade_date: str, period: int = 20) -> Optional[float]:
        """平均成交额（亿元）"""
        end_date = datetime.strptime(trade_date, "%Y-%m-%d")
        start_date = (end_date - timedelta(days=period * 2)).strftime("%Y-%m-%d")

        df = self.get_stock_daily(ts_code, start_date, trade_date)
        if df.empty or len(df) < period:
            return None

        df = df.sort_values('trade_date')
        amounts = df['amount'].values[-period:]

        return np.mean(amounts) / 1e8  # 转换为亿元

    def calc_avg_turnover(self, ts_code: str, trade_date: str, period: int = 20) -> Optional[float]:
        """平均换手率"""
        end_date = datetime.strptime(trade_date, "%Y-%m-%d")
        start_date = (end_date - timedelta(days=period * 2)).strftime("%Y-%m-%d")

        df = self.get_stock_daily(ts_code, start_date, trade_date)
        if df.empty or len(df) < period:
            return None

        df = df.sort_values('trade_date')

        # 换手率 = 成交量 / 总股本 * 100
        # 简化：使用成交额/市值估算
        amounts = df['amount'].values[-period:]

        return np.mean(amounts) * 100 if len(amounts) > 0 else None

    def calc_illiquidity(self, ts_code: str, trade_date: str, period: int = 20) -> Optional[float]:
        """非流动性指标 = |收益率| / 成交额"""
        end_date = datetime.strptime(trade_date, "%Y-%m-%d")
        start_date = (end_date - timedelta(days=period * 2)).strftime("%Y-%m-%d")

        df = self.get_stock_daily(ts_code, start_date, trade_date)
        if df.empty or len(df) < period:
            return None

        df = df.sort_values('trade_date')
        df = df.tail(period)

        # 计算每日非流动性
        illiq = []
        for i in range(1, len(df)):
            ret = abs(df['pct_chg'].iloc[i] / 100)
            amt = df['amount'].iloc[i]
            if amt and amt > 0:
                illiq.append(ret / amt)

        return np.mean(illiq) if illiq else None


class FactorEngine:
    """因子计算引擎"""

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.quality = QualityFactorCalculator(self.db)
        self.valuation = ValuationFactorCalculator(self.db)
        self.momentum = MomentumFactorCalculator(self.db)
        self.growth = GrowthFactorCalculator(self.db)
        self.risk = RiskFactorCalculator(self.db)
        self.liquidity = LiquidityFactorCalculator(self.db)

    def calculate_factor(self, factor_code: str, ts_code: str, trade_date: str) -> Optional[float]:
        """
        根据因子代码计算因子值

        Args:
            factor_code: 因子代码
            ts_code: 股票代码
            trade_date: 交易日期

        Returns:
            因子值
        """
        factor_map = {
            # 质量因子
            'ROE': lambda: self.quality.calc_roe(ts_code),
            'ROA': lambda: self.quality.calc_roa(ts_code),
            'GROSS_MARGIN': lambda: self.quality.calc_gross_margin(ts_code),
            'NET_MARGIN': lambda: self.quality.calc_net_margin(ts_code),
            # 估值因子
            'PE_TTM': lambda: self.valuation.calc_pe_ttm(ts_code, trade_date),
            'PB': lambda: self.valuation.calc_pb(ts_code, trade_date),
            'PS_TTM': lambda: self.valuation.calc_ps_ttm(ts_code, trade_date),
            # 动量因子
            'MOM_20D': lambda: self.momentum.calc_momentum_20d(ts_code, trade_date),
            'MOM_60D': lambda: self.momentum.calc_momentum_60d(ts_code, trade_date),
            'MOM_120D': lambda: self.momentum.calc_momentum_120d(ts_code, trade_date),
            # 成长因子
            'REVENUE_GROWTH': lambda: self.growth.calc_revenue_growth(ts_code),
            'PROFIT_GROWTH': lambda: self.growth.calc_profit_growth(ts_code),
            # 风险因子
            'VOL_20D': lambda: self.risk.calc_volatility_20d(ts_code, trade_date),
            'VOL_60D': lambda: self.risk.calc_volatility_60d(ts_code, trade_date),
            # 流动性因子
            'TURNOVER_20D': lambda: self.liquidity.calc_avg_turnover(ts_code, trade_date),
            'AMOUNT_20D': lambda: self.liquidity.calc_avg_amount(ts_code, trade_date),
        }

        calculator = factor_map.get(factor_code)
        if not calculator:
            logger.warning(f"Unknown factor code: {factor_code}")
            return None

        try:
            return calculator()
        except Exception as e:
            logger.error(f"Error calculating factor {factor_code} for {ts_code}: {e}")
            return None

    def calculate_all_factors(self, ts_codes: List[str], trade_date: str,
                             factor_codes: List[str] = None) -> pd.DataFrame:
        """
        批量计算多只股票的多个因子

        Args:
            ts_codes: 股票代码列表
            trade_date: 交易日期
            factor_codes: 因子代码列表，默认计算所有因子

        Returns:
            DataFrame，行为股票，列为因子
        """
        if factor_codes is None:
            factor_codes = [
                'ROE', 'ROA', 'GROSS_MARGIN', 'NET_MARGIN',
                'PE_TTM', 'PB', 'PS_TTM',
                'MOM_20D', 'MOM_60D', 'MOM_120D',
                'REVENUE_GROWTH', 'PROFIT_GROWTH',
                'VOL_20D', 'VOL_60D',
                'TURNOVER_20D', 'AMOUNT_20D'
            ]

        results = []
        for ts_code in ts_codes:
            row = {'ts_code': ts_code}
            for factor_code in factor_codes:
                row[factor_code] = self.calculate_factor(factor_code, ts_code, trade_date)
            results.append(row)

        return pd.DataFrame(results)

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


@with_db
def run_factor_calculation(factor_id: int, trade_date: str, ts_codes: List[str], db: Session = None) -> List[FactorValue]:
    """
    运行因子计算并保存结果

    Args:
        factor_id: 因子ID
        trade_date: 交易日期
        ts_codes: 股票代码列表
        db: 数据库会话

    Returns:
        因子值列表
    """
    # 获取因子信息
    factor = db.query(Factor).filter(Factor.id == factor_id).first()
    if not factor:
        logger.error(f"Factor {factor_id} not found")
        return []

    engine = FactorEngine(db)
    results = []

    for ts_code in ts_codes:
        value = engine.calculate_factor(factor.factor_code, ts_code, trade_date)

        if value is not None:
            # 检查是否已存在
            existing = db.query(FactorValue).filter(
                FactorValue.factor_id == factor_id,
                FactorValue.trade_date == trade_date,
                FactorValue.security_id == ts_code  # 简化：使用 ts_code 作为 security_id
            ).first()

            if existing:
                existing.value = value
                existing.is_valid = True
            else:
                fv = FactorValue(
                    factor_id=factor_id,
                    trade_date=trade_date,
                    security_id=ts_code,  # 简化处理
                    value=value,
                    is_valid=True
                )
                db.add(fv)
                results.append(fv)

    db.commit()
    logger.info(f"Calculated {len(results)} factor values for {factor.factor_code} on {trade_date}")

    return results
