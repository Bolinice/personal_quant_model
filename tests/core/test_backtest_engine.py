"""回测引擎核心逻辑测试 — T+1/涨跌停/交易成本"""

from datetime import date

from app.core.backtest_engine import (
    ABShareBacktestEngine,
    BacktestState,
    TransactionCost,
)


class TestTradingRules:
    """A股交易规则测试"""

    def setup_method(self):
        self.engine = ABShareBacktestEngine()

    def test_get_board_type(self):
        """板块类型判断"""
        assert self.engine.get_board_type("300001.SZ") == "gem"
        assert self.engine.get_board_type("688001.SH") == "star"
        assert self.engine.get_board_type("430001.BJ") == "north"
        assert self.engine.get_board_type("600001.SH") == "main"
        assert self.engine.get_board_type("000001.SZ") == "main"

    def test_is_limit_up(self):
        """涨停判断"""
        assert self.engine.is_limit_up(10.0, "main") is True
        assert self.engine.is_limit_up(9.99, "main") is True  # 0.01%误差容忍
        assert self.engine.is_limit_up(9.98, "main") is False
        assert self.engine.is_limit_up(20.0, "gem") is True
        assert self.engine.is_limit_up(5.0, "main", is_st=True) is True

    def test_is_limit_down(self):
        """跌停判断"""
        assert self.engine.is_limit_down(-10.0, "main") is True
        assert self.engine.is_limit_down(-9.99, "main") is True
        assert self.engine.is_limit_down(-9.98, "main") is False
        assert self.engine.is_limit_down(-5.0, "main", is_st=True) is True

    def test_round_lot(self):
        """100股整数倍"""
        assert self.engine.round_lot(150) == 100
        assert self.engine.round_lot(200) == 200
        assert self.engine.round_lot(99) == 0
        assert self.engine.round_lot(250) == 200


class TestTransactionCost:
    """交易成本计算测试"""

    def setup_method(self):
        self.cost = TransactionCost()

    def test_buy_cost(self):
        """买入成本计算"""
        result = self.cost.calc_buy_cost(100000)
        assert result["stamp_tax"] == 0.0  # 买入无印花税
        assert result["commission"] >= 5.0  # 最低5元
        assert result["total_cost"] > 0

    def test_sell_cost(self):
        """卖出成本计算(含印花税)"""
        result = self.cost.calc_sell_cost(100000)
        assert result["stamp_tax"] == 100.0  # 千1印花税
        assert result["total_cost"] > 0

    def test_min_commission(self):
        """最低佣金5元"""
        result = self.cost.calc_buy_cost(100)  # 小额交易
        assert result["commission"] == 5.0  # 最低5元

    def test_participation_rate_slippage(self):
        """参与率滑点模型"""
        # 有成交量和波动率时使用参与率模型
        result = self.cost.calc_buy_cost(100000, daily_volume=1000000, volatility=0.02)
        assert result["slippage"] > 0
        # 无成交数据时退化为固定滑点
        result_fixed = self.cost.calc_buy_cost(100000)
        assert result_fixed["slippage"] == 100.0  # 0.1%固定滑点


class TestT1Rule:
    """T+1规则测试"""

    def setup_method(self):
        self.engine = ABShareBacktestEngine()
        self.state = BacktestState()

    def test_t1_buy_cannot_sell_same_day(self):
        """当日买入不能当日卖出"""
        self.engine.execute_buy(
            self.state,
            "600001.SH",
            10000,
            10.0,
            date(2025, 1, 15),
            stock_data={"pct_chg": 0, "is_suspended": False, "is_st": False, "is_delist": False},
        )
        # 当日卖出应失败
        result = self.engine.execute_sell(
            self.state,
            "600001.SH",
            100,
            10.0,
            date(2025, 1, 15),
            stock_data={"pct_chg": 0, "is_suspended": False, "is_st": False, "is_delist": False},
        )
        assert result is None  # T+1限制

    def test_t1_can_sell_next_day(self):
        """次日可以卖出前日买入的股票"""
        self.engine.execute_buy(
            self.state,
            "600001.SH",
            10000,
            10.0,
            date(2025, 1, 15),
            stock_data={"pct_chg": 0, "is_suspended": False, "is_st": False, "is_delist": False},
        )
        # 重置shares_bought_today (模拟次日)
        for pos in self.state.positions.values():
            pos.shares_bought_today = 0
        result = self.engine.execute_sell(
            self.state,
            "600001.SH",
            100,
            10.5,
            date(2025, 1, 16),
            stock_data={"pct_chg": 5, "is_suspended": False, "is_st": False, "is_delist": False},
        )
        assert result is not None  # T+1后可卖出
