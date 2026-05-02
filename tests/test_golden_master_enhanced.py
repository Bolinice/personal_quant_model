"""
Golden Master 测试 - 增强版

覆盖核心计算模块的真实输出：
1. 因子计算纯函数（app/core/pure/factor_math.py）
2. 风险模型计算（协方差矩阵、VaR/CVaR）
3. 回测引擎关键指标（收益率、夏普比率、最大回撤）

运行:
  pytest tests/test_golden_master_enhanced.py                    # 验证
  pytest tests/test_golden_master_enhanced.py --update-golden    # 更新参考数据
"""

import numpy as np
import pandas as pd
import pytest

from app.core.pure.factor_math import (
    calc_amihud_illiquidity,
    calc_bp,
    calc_current_ratio,
    calc_ep_ttm,
    calc_gross_profit_margin,
    calc_momentum_skip,
    calc_net_profit_margin,
    calc_reversal_1m,
    calc_roa,
    calc_roe,
    calc_rsi,
    calc_sloan_accrual,
    calc_turnover_mean,
    calc_volatility_annualized,
    calc_yoy_growth,
    calc_zero_return_ratio,
)
from app.core.risk_model import RiskModel
from tests.conftest_golden import compare_with_golden, save_golden

# ==================== 测试数据生成 ====================


def _make_deterministic_price_data(n_stocks: int = 30, n_days: int = 252) -> pd.DataFrame:
    """生成确定性的价格数据（用于因子计算）"""
    rng = np.random.RandomState(42)

    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    codes = [f"{i:06d}.SZ" for i in range(1, n_stocks + 1)]

    rows = []
    for code_idx, code in enumerate(codes):
        # 每只股票有不同的趋势和波动特征
        base_price = 10.0 + code_idx * 0.5
        trend = 0.0002 * (code_idx % 3 - 1)  # -0.0002, 0, 0.0002
        volatility = 0.015 + 0.005 * (code_idx % 5)

        prices = []
        price = base_price
        for day in range(n_days):
            # 确定性随机游走
            ret = trend + volatility * rng.randn()
            price = price * (1 + ret)
            prices.append(price)

        for day, (date, price) in enumerate(zip(dates, prices)):
            # 生成配套的成交量和财务数据
            volume = 1000000 * (1 + 0.3 * rng.randn())
            amount = price * volume

            rows.append({
                "trade_date": date.strftime("%Y%m%d"),
                "ts_code": code,
                "close": price,
                "open": price * (1 + 0.001 * rng.randn()),
                "high": price * (1 + abs(0.002 * rng.randn())),
                "low": price * (1 - abs(0.002 * rng.randn())),
                "volume": volume,
                "amount": amount,
                "turnover_rate": 2.0 + rng.randn(),
                "pct_chg": 0.0 if day == 0 else (prices[day] / prices[day-1] - 1) * 100,
            })

    return pd.DataFrame(rows)


def _make_deterministic_financial_data(n_stocks: int = 30) -> pd.DataFrame:
    """生成确定性的财务数据"""
    rng = np.random.RandomState(42)
    codes = [f"{i:06d}.SZ" for i in range(1, n_stocks + 1)]

    rows = []
    for code_idx, code in enumerate(codes):
        # 每只股票有不同的财务特征
        base_roe = 0.08 + 0.02 * (code_idx % 10)
        base_margin = 0.25 + 0.05 * (code_idx % 8)

        rows.append({
            "ts_code": code,
            "total_mv": 1e9 * (10 + code_idx * 2),
            "net_profit_ttm": 1e8 * (1 + code_idx * 0.1),
            "net_profit_ttm_prev": 1e8 * (0.9 + code_idx * 0.1),
            "total_assets": 1e9 * (5 + code_idx),
            "total_equity": 1e9 * (2 + code_idx * 0.5),
            "total_equity_prev": 1e9 * (1.9 + code_idx * 0.5),
            "revenue_ttm": 1e9 * (3 + code_idx * 0.3),
            "revenue_ttm_prev": 1e9 * (2.8 + code_idx * 0.3),
            "operating_cost": 1e9 * (2 + code_idx * 0.2),
            "current_assets": 1e9 * (3 + code_idx * 0.4),
            "current_liabilities": 1e9 * (1.5 + code_idx * 0.2),
            "total_liabilities": 1e9 * (3 + code_idx * 0.5),
            "operating_cashflow": 1e8 * (1.2 + code_idx * 0.15),
            "cashflow_ttm": 1e8 * (1.1 + code_idx * 0.12),
        })

    return pd.DataFrame(rows)


def _compute_factor_values(price_data: pd.DataFrame, financial_data: pd.DataFrame) -> pd.DataFrame:
    """计算因子值（使用真实的纯函数）"""
    results = []

    # 按股票分组计算
    for ts_code, group in price_data.groupby("ts_code"):
        group = group.sort_values("trade_date").reset_index(drop=True)
        fin = financial_data[financial_data["ts_code"] == ts_code].iloc[0]

        # 提取时间序列
        close = group["close"]
        volume = group["volume"]
        amount = group["amount"]
        turnover_rate = group["turnover_rate"]
        pct_chg = group["pct_chg"]

        # 计算各类因子
        momentum_skip = calc_momentum_skip(close, skip_period=20, lookback_period=240)
        reversal_1m = calc_reversal_1m(close)
        volatility = calc_volatility_annualized(close)
        turnover_mean_val = calc_turnover_mean(turnover_rate, period=20)
        amihud = calc_amihud_illiquidity(close, volume, period=20)
        zero_return = calc_zero_return_ratio(close, period=20)

        # 估值因子
        ep_ttm = calc_ep_ttm(fin["net_profit_ttm"], fin["total_mv"])
        bp = calc_bp(fin["total_equity"], fin["total_mv"])

        # 质量因子
        roe = calc_roe(fin["net_profit_ttm"], fin["total_equity"], fin.get("total_equity_prev"))
        roa = calc_roa(fin["net_profit_ttm"], fin["total_assets"])
        gross_margin = calc_gross_profit_margin(fin["revenue_ttm"], fin["operating_cost"])
        net_margin = calc_net_profit_margin(fin["net_profit_ttm"], fin["revenue_ttm"])
        current_ratio = calc_current_ratio(fin["current_assets"], fin["current_liabilities"])

        # 成长因子
        revenue_growth = calc_yoy_growth(fin["revenue_ttm"], fin["revenue_ttm_prev"])

        # 应计因子
        sloan_accrual = calc_sloan_accrual(
            fin["net_profit_ttm"],
            fin["operating_cashflow"],
            fin["total_assets"],
            fin.get("total_assets")  # 简化：使用当期资产
        )

        # 技术指标
        rsi_val = calc_rsi(close, period=14)

        # 取最后一个有效值
        results.append({
            "ts_code": ts_code,
            "momentum_skip": momentum_skip.iloc[-1] if len(momentum_skip) > 0 else np.nan,
            "reversal_1m": reversal_1m.iloc[-1] if len(reversal_1m) > 0 else np.nan,
            "volatility": volatility.iloc[-1] if len(volatility) > 0 else np.nan,
            "turnover_mean": turnover_mean_val.iloc[-1] if len(turnover_mean_val) > 0 else np.nan,
            "amihud_illiquidity": amihud.iloc[-1] if len(amihud) > 0 else np.nan,
            "zero_return_ratio": zero_return.iloc[-1] if len(zero_return) > 0 else np.nan,
            "ep_ttm": ep_ttm,
            "bp": bp,
            "roe": roe,
            "roa": roa,
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "current_ratio": current_ratio,
            "revenue_growth": revenue_growth,
            "sloan_accrual": sloan_accrual,
            "rsi": rsi_val.iloc[-1] if len(rsi_val) > 0 else np.nan,
        })

    return pd.DataFrame(results)


def _compute_risk_metrics(returns: pd.DataFrame) -> dict:
    """计算风险指标（使用真实的风险模型）"""
    risk_model = RiskModel()

    # 协方差矩阵估计
    sample_cov = risk_model.sample_covariance(returns)
    lw_cov = risk_model.ledoit_wolf_shrinkage(returns, shrinkage_target="identity")
    ewma_cov = risk_model.ewma_covariance(returns, halflife=60)

    # VaR/CVaR计算（使用市场组合）
    portfolio_returns = returns.mean(axis=1)
    hist_var_95 = risk_model.historical_var(portfolio_returns, confidence=0.95)
    hist_var_99 = risk_model.historical_var(portfolio_returns, confidence=0.99)
    cvar_95 = risk_model.conditional_var(portfolio_returns, confidence=0.95)
    cvar_99 = risk_model.conditional_var(portfolio_returns, confidence=0.99)

    # 组合风险指标（等权组合）
    n_assets = len(returns.columns)
    equal_weights = np.ones(n_assets) / n_assets

    portfolio_vol_sample = risk_model.portfolio_volatility(equal_weights, sample_cov.values)
    portfolio_vol_lw = risk_model.portfolio_volatility(equal_weights, lw_cov.values)
    portfolio_vol_ewma = risk_model.portfolio_volatility(equal_weights, ewma_cov.values)

    return {
        "sample_cov_trace": np.trace(sample_cov.values),
        "lw_cov_trace": np.trace(lw_cov.values),
        "ewma_cov_trace": np.trace(ewma_cov.values),
        "hist_var_95": hist_var_95,
        "hist_var_99": hist_var_99,
        "cvar_95": cvar_95,
        "cvar_99": cvar_99,
        "portfolio_vol_sample": portfolio_vol_sample,
        "portfolio_vol_lw": portfolio_vol_lw,
        "portfolio_vol_ewma": portfolio_vol_ewma,
    }


# ==================== Golden Master 测试 ====================


class TestGoldenMasterFactorCalculation:
    """因子计算 Golden Master 测试"""

    def test_factor_calculation_golden(self, update_golden):
        """验证因子计算输出的一致性"""
        # 生成确定性数据
        price_data = _make_deterministic_price_data(n_stocks=30, n_days=252)
        financial_data = _make_deterministic_financial_data(n_stocks=30)

        # 计算因子
        factor_values = _compute_factor_values(price_data, financial_data)

        if update_golden:
            save_golden("factor_calculation", factor_values)
        else:
            compare_with_golden("factor_calculation", factor_values, atol=1e-8)


class TestGoldenMasterRiskModel:
    """风险模型 Golden Master 测试"""

    def test_risk_model_golden(self, update_golden):
        """验证风险模型计算的一致性"""
        # 生成确定性收益率数据
        rng = np.random.RandomState(42)
        n_stocks = 30
        n_days = 252

        dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
        returns_data = {}

        for i in range(n_stocks):
            code = f"{i:06d}.SZ"
            # 每只股票有不同的收益特征
            mu = 0.0001 * (i % 5 - 2)  # -0.0002 to 0.0002
            sigma = 0.015 + 0.005 * (i % 3)
            returns_data[code] = rng.normal(mu, sigma, n_days)

        returns = pd.DataFrame(returns_data, index=dates)

        # 计算风险指标
        risk_metrics = _compute_risk_metrics(returns)
        risk_df = pd.DataFrame([risk_metrics])

        if update_golden:
            save_golden("risk_model", risk_df)
        else:
            compare_with_golden("risk_model", risk_df, atol=1e-8)


class TestGoldenMasterBacktestMetrics:
    """回测指标 Golden Master 测试"""

    def test_backtest_metrics_golden(self, update_golden):
        """验证回测指标计算的一致性"""
        # 生成确定性的回测收益序列
        rng = np.random.RandomState(42)
        n_days = 252

        dates = pd.date_range("2024-01-01", periods=n_days, freq="B")

        # 策略收益：有正向漂移和波动
        strategy_returns = rng.normal(0.0005, 0.015, n_days)
        benchmark_returns = rng.normal(0.0003, 0.012, n_days)

        # 计算累计收益
        strategy_cum = (1 + pd.Series(strategy_returns)).cumprod()
        benchmark_cum = (1 + pd.Series(benchmark_returns)).cumprod()

        # 计算关键指标
        from app.core.pure.risk_calc import (
            calc_max_drawdown,
            calc_sharpe_ratio,
            calc_sortino_ratio,
        )

        strategy_series = pd.Series(strategy_returns)

        sharpe = calc_sharpe_ratio(strategy_series, annual_factor=252)
        sortino = calc_sortino_ratio(strategy_series, annual_factor=252)
        max_dd = calc_max_drawdown(strategy_cum)

        # 年化收益
        total_return = strategy_cum.iloc[-1] - 1
        annual_return = (1 + total_return) ** (252 / n_days) - 1

        # 超额收益
        excess_returns = strategy_returns - benchmark_returns
        excess_cum = (1 + pd.Series(excess_returns)).cumprod()
        excess_total = excess_cum.iloc[-1] - 1

        metrics = pd.DataFrame([{
            "total_return": total_return,
            "annual_return": annual_return,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_dd,
            "excess_return": excess_total,
            "volatility": strategy_series.std() * np.sqrt(252),
        }])

        if update_golden:
            save_golden("backtest_metrics", metrics)
        else:
            compare_with_golden("backtest_metrics", metrics, atol=1e-8)


class TestGoldenMasterIntegration:
    """集成测试：端到端流程"""

    def test_end_to_end_pipeline_golden(self, update_golden):
        """验证完整流程的输出一致性"""
        # 1. 生成数据
        price_data = _make_deterministic_price_data(n_stocks=20, n_days=126)
        financial_data = _make_deterministic_financial_data(n_stocks=20)

        # 2. 计算因子
        factor_values = _compute_factor_values(price_data, financial_data)

        # 3. 构建简单的收益率矩阵
        returns_pivot = price_data.pivot(index="trade_date", columns="ts_code", values="pct_chg") / 100
        returns_pivot = returns_pivot.fillna(0)

        # 4. 计算风险指标
        risk_metrics = _compute_risk_metrics(returns_pivot)

        # 5. 合并结果
        pipeline_output = pd.DataFrame([{
            "n_stocks": len(factor_values),
            "avg_momentum": factor_values["momentum_skip"].mean(),
            "avg_volatility": factor_values["volatility"].mean(),
            "avg_roe": factor_values["roe"].mean(),
            "portfolio_vol": risk_metrics["portfolio_vol_sample"],
            "var_95": risk_metrics["hist_var_95"],
        }])

        if update_golden:
            save_golden("end_to_end_pipeline", pipeline_output)
        else:
            compare_with_golden("end_to_end_pipeline", pipeline_output, atol=1e-8)
