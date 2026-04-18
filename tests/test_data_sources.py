"""
数据源模块单元测试
覆盖：BaseDataSource、DataSourceManager、TushareDataSource、AKShareDataSource、
      CrawlerDataSource、DataNormalizer、DataCleaner
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock


# ==================== 辅助：创建测试用 DataFrame ====================

def make_stock_daily_df(n=10, ts_code=None):
    """生成模拟股票日线数据"""
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'trade_date': dates.strftime('%Y-%m-%d'),
        'open': np.random.uniform(10, 20, n).round(2),
        'high': np.random.uniform(20, 25, n).round(2),
        'low': np.random.uniform(5, 10, n).round(2),
        'close': np.random.uniform(10, 20, n).round(2),
        'pre_close': np.random.uniform(10, 20, n).round(2),
        'volume': np.random.randint(100000, 1000000, n),
        'amount': np.random.uniform(1e6, 1e7, n).round(2),
        'pct_chg': np.random.uniform(-5, 5, n).round(2),
    })
    if ts_code:
        df['ts_code'] = ts_code
    return df


def make_index_daily_df(n=10):
    """生成模拟指数日线数据"""
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    return pd.DataFrame({
        'trade_date': dates.strftime('%Y-%m-%d'),
        'open': np.random.uniform(3000, 3100, n).round(2),
        'high': np.random.uniform(3100, 3200, n).round(2),
        'low': np.random.uniform(2900, 3000, n).round(2),
        'close': np.random.uniform(3000, 3100, n).round(2),
        'pre_close': np.random.uniform(3000, 3100, n).round(2),
        'volume': np.random.randint(1e8, 1e9, n),
        'amount': np.random.uniform(1e10, 1e11, n).round(2),
        'pct_chg': np.random.uniform(-2, 2, n).round(2),
    })


def make_stock_basic_df(n=5):
    """生成模拟股票基础信息"""
    codes = [f'{600000+i:06d}' for i in range(n)]
    return pd.DataFrame({
        'ts_code': [f'{c}.SH' for c in codes],
        'symbol': codes,
        'name': [f'测试股票{i}' for i in range(n)],
        'industry': ['银行', '地产', '科技', '医药', '消费'],
        'market': ['SH'] * n,
        'list_date': ['2000-01-01'] * n,
        'status': ['L'] * n,
    })


def make_trading_calendar_df(n=10):
    """生成模拟交易日历"""
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    return pd.DataFrame({
        'trade_date': dates.strftime('%Y-%m-%d'),
        'is_open': [1] * n,
        'pretrade_date': [None] + dates[:-1].strftime('%Y-%m-%d').tolist(),
    })


# ==================== TestBaseDataSource ====================

class TestBaseDataSource:
    """数据源基类测试"""

    def _make_source(self, **kwargs):
        """创建可实例化的 BaseDataSource 子类"""
        from app.data_sources.base import BaseDataSource as _Base

        class ConcreteSource(_Base):
            def connect(self):
                return True
            def get_stock_basic(self, **kw):
                return pd.DataFrame()
            def get_stock_daily(self, ts_code=None, start_date=None, end_date=None, **kw):
                return pd.DataFrame()
            def get_index_daily(self, ts_code=None, start_date=None, end_date=None, **kw):
                return pd.DataFrame()
            def get_financial_data(self, ts_code=None, start_date=None, end_date=None, **kw):
                return pd.DataFrame()
            def get_trading_calendar(self, exchange='SSE', start_date=None, end_date=None):
                return pd.DataFrame()

        return ConcreteSource(**kwargs)

    def test_default_rate_limit(self):
        source = self._make_source()
        assert source.rate_limit == 200
        assert source.max_retries == 3

    def test_custom_rate_limit(self):
        source = self._make_source(rate_limit=100, max_retries=5)
        assert source.rate_limit == 100
        assert source.max_retries == 5

    def test_rate_limit_check_increments(self):
        source = self._make_source()
        source._rate_limit_check()
        assert source._call_count == 1
        source._rate_limit_check()
        assert source._call_count == 2

    def test_incremental_sync_already_up_to_date(self):
        source = self._make_source()
        result = source.incremental_sync('stock_daily', date.today())
        assert result.success
        assert result.records_fetched == 0

    def test_incremental_sync_with_date_range(self):
        source = self._make_source()
        last_sync = date.today() - timedelta(days=5)
        result = source.incremental_sync('stock_daily', last_sync)
        assert result.success

    def test_incremental_sync_unknown_data_type(self):
        source = self._make_source()
        last_sync = date.today() - timedelta(days=5)
        result = source.incremental_sync('unknown_type', last_sync)
        assert not result.success
        assert 'Unknown data type' in result.error_message

    def test_sync_result_defaults(self):
        from app.data_sources.base import SyncResult
        result = SyncResult()
        assert result.success is True
        assert result.records_fetched == 0
        assert result.records_saved == 0
        assert result.records_updated == 0
        assert result.records_failed == 0
        assert result.error_message is None
        assert result.duration_seconds == 0.0
        assert result.details == {}

    def test_sync_result_with_values(self):
        from app.data_sources.base import SyncResult
        result = SyncResult(
            success=True,
            records_fetched=100,
            records_saved=95,
            records_updated=5,
            duration_seconds=1.5,
        )
        assert result.records_fetched == 100
        assert result.records_saved == 95

    def test_retry_call_success(self):
        source = self._make_source()
        result = source._retry_call(lambda: 42)
        assert result == 42

    def test_retry_call_with_retries(self):
        source = self._make_source(max_retries=3)
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        with patch('time.sleep'):
            result = source._retry_call(flaky_func)
        assert result == "success"
        assert call_count == 3

    def test_retry_call_exhausted(self):
        source = self._make_source(max_retries=2)

        def always_fail():
            raise ValueError("permanent error")

        with patch('time.sleep'):
            with pytest.raises(ValueError, match="permanent error"):
                source._retry_call(always_fail)


# ==================== TestDataSourceManager ====================

class TestDataSourceManager:
    """数据源管理器测试"""

    def test_empty_manager(self):
        from app.data_sources.base import DataSourceManager
        manager = DataSourceManager()
        assert manager.get_primary() is None
        assert manager.get('nonexistent') is None

    def test_register_and_get(self):
        from app.data_sources.base import DataSourceManager, BaseDataSource

        class MockSource(BaseDataSource):
            def connect(self): return True
            def get_stock_basic(self, **kw): return pd.DataFrame()
            def get_stock_daily(self, **kw): return pd.DataFrame()
            def get_index_daily(self, **kw): return pd.DataFrame()
            def get_financial_data(self, **kw): return pd.DataFrame()
            def get_trading_calendar(self, **kw): return pd.DataFrame()

        manager = DataSourceManager()
        source = MockSource()
        manager.register('test', source)
        assert manager.get('test') is source
        # No primary set, so get_primary falls back to first
        assert manager.get_primary() is source

    def test_register_primary(self):
        from app.data_sources.base import DataSourceManager, BaseDataSource

        class MockSource(BaseDataSource):
            def connect(self): return True
            def get_stock_basic(self, **kw): return pd.DataFrame()
            def get_stock_daily(self, **kw): return pd.DataFrame()
            def get_index_daily(self, **kw): return pd.DataFrame()
            def get_financial_data(self, **kw): return pd.DataFrame()
            def get_trading_calendar(self, **kw): return pd.DataFrame()

        manager = DataSourceManager()
        source = MockSource()
        manager.register('primary', source, is_primary=True)
        assert manager.get_primary() is source

    def test_get_primary_fallback(self):
        from app.data_sources.base import DataSourceManager, BaseDataSource

        class MockSource(BaseDataSource):
            def connect(self): return True
            def get_stock_basic(self, **kw): return pd.DataFrame()
            def get_stock_daily(self, **kw): return pd.DataFrame()
            def get_index_daily(self, **kw): return pd.DataFrame()
            def get_financial_data(self, **kw): return pd.DataFrame()
            def get_trading_calendar(self, **kw): return pd.DataFrame()

        manager = DataSourceManager()
        source = MockSource()
        manager.register('first', source)
        # No primary set, fallback to first
        assert manager.get_primary() is source

    def test_connect_all(self):
        from app.data_sources.base import DataSourceManager, BaseDataSource

        class GoodSource(BaseDataSource):
            def connect(self): return True
            def get_stock_basic(self, **kw): return pd.DataFrame()
            def get_stock_daily(self, **kw): return pd.DataFrame()
            def get_index_daily(self, **kw): return pd.DataFrame()
            def get_financial_data(self, **kw): return pd.DataFrame()
            def get_trading_calendar(self, **kw): return pd.DataFrame()

        class BadSource(BaseDataSource):
            def connect(self): return False
            def get_stock_basic(self, **kw): return pd.DataFrame()
            def get_stock_daily(self, **kw): return pd.DataFrame()
            def get_index_daily(self, **kw): return pd.DataFrame()
            def get_financial_data(self, **kw): return pd.DataFrame()
            def get_trading_calendar(self, **kw): return pd.DataFrame()

        manager = DataSourceManager()
        manager.register('good', GoodSource())
        manager.register('bad', BadSource())
        status = manager.connect_all()
        assert status['good'] is True
        assert status['bad'] is False

    def test_connect_all_exception(self):
        from app.data_sources.base import DataSourceManager, BaseDataSource

        class ErrorSource(BaseDataSource):
            def connect(self): raise RuntimeError("connection error")
            def get_stock_basic(self, **kw): return pd.DataFrame()
            def get_stock_daily(self, **kw): return pd.DataFrame()
            def get_index_daily(self, **kw): return pd.DataFrame()
            def get_financial_data(self, **kw): return pd.DataFrame()
            def get_trading_calendar(self, **kw): return pd.DataFrame()

        manager = DataSourceManager()
        manager.register('error', ErrorSource())
        status = manager.connect_all()
        assert status['error'] is False


# ==================== TestTushareDataSource ====================

class TestTushareDataSource:
    """Tushare 数据源测试（mock API）"""

    def _make_source(self, connected=True):
        from app.data_sources.tushare_source import TushareDataSource
        source = TushareDataSource(token='test_token')
        source._connected = connected
        source._pro = MagicMock()
        return source

    def test_init(self):
        from app.data_sources.tushare_source import TushareDataSource
        source = TushareDataSource(token='my_token')
        assert source.token == 'my_token'
        assert source._pro is None

    def test_connect_success(self):
        from app.data_sources.tushare_source import TushareDataSource
        with patch('tushare.set_token'), \
             patch('tushare.pro_api') as mock_pro_api:
            mock_pro = MagicMock()
            mock_pro.stock_basic.return_value = pd.DataFrame({'ts_code': ['600000.SH']})
            mock_pro_api.return_value = mock_pro

            source = TushareDataSource(token='test')
            result = source.connect()
            assert result is True
            assert source._connected is True

    def test_connect_failure(self):
        from app.data_sources.tushare_source import TushareDataSource
        with patch('tushare.set_token'), \
             patch('tushare.pro_api') as mock_pro_api:
            mock_pro_api.side_effect = Exception("API error")
            source = TushareDataSource(token='test')
            result = source.connect()
            assert result is False

    def test_get_stock_daily(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'trade_date': ['20240102', '20240103'],
            'open': [10.0, 10.5],
            'high': [11.0, 11.0],
            'low': [9.5, 10.0],
            'close': [10.5, 10.8],
            'vol': [100000, 120000],
            'amount': [1e6, 1.2e6],
            'pct_chg': [1.0, 2.86],
            'pre_close': [10.0, 10.5],
        })
        source._pro.daily.return_value = raw_df

        result = source.get_stock_daily('600000.SH', '2024-01-02', '2024-01-03')
        assert not result.empty
        assert 'trade_date' in result.columns
        assert result['trade_date'].iloc[0] == '2024-01-02'

    def test_get_stock_daily_not_connected(self):
        source = self._make_source(connected=False)
        result = source.get_stock_daily('600000.SH', '2024-01-01', '2024-01-10')
        assert result.empty

    def test_get_index_daily(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'trade_date': ['20240102', '20240103'],
            'open': [3000, 3010],
            'high': [3020, 3030],
            'low': [2990, 3000],
            'close': [3010, 3020],
            'vol': [1e8, 1.1e8],
            'amount': [1e10, 1.1e10],
            'pct_chg': [0.33, 0.33],
            'pre_close': [3000, 3010],
        })
        source._pro.index_daily.return_value = raw_df

        result = source.get_index_daily('000001.SH', '2024-01-02', '2024-01-03')
        assert not result.empty
        assert result['trade_date'].iloc[0] == '2024-01-02'

    def test_get_stock_basic(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'ts_code': ['600000.SH', '000001.SZ'],
            'symbol': ['600000', '000001'],
            'name': ['浦发银行', '平安银行'],
            'area': ['上海', '深圳'],
            'industry': ['银行', '银行'],
            'market': ['主板', '主板'],
            'list_date': ['19991110', '19910403'],
            'delist_date': [None, None],
            'is_hs': ['S', 'S'],
        })
        source._pro.stock_basic.return_value = raw_df

        result = source.get_stock_basic()
        assert not result.empty
        assert 'ts_code' in result.columns
        assert 'status' in result.columns

    def test_get_trading_calendar(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'cal_date': ['20240102', '20240103'],
            'is_open': [1, 1],
            'pretrade_date': ['20231229', '20240102'],
        })
        source._pro.trade_cal.return_value = raw_df

        result = source.get_trading_calendar('2024-01-02', '2024-01-03')
        assert not result.empty
        assert result['trade_date'].iloc[0] == '2024-01-02'

    def test_get_stock_daily_batch(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'trade_date': ['20240102'],
            'open': [10.0], 'high': [11.0], 'low': [9.5], 'close': [10.5],
            'vol': [100000], 'amount': [1e6], 'pct_chg': [1.0], 'pre_close': [10.0],
        })
        source._pro.daily.return_value = raw_df

        result = source.get_stock_daily_batch(['600000.SH', '000001.SZ'], '2024-01-02', '2024-01-02')
        assert not result.empty
        assert 'ts_code' in result.columns

    def test_get_financial_indicator(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'ts_code': ['600000.SH'],
            'end_date': ['20231231'],
            'ann_date': ['20240330'],
            'roe': [10.5],
            'roa': [0.8],
            'grossprofit_margin': [40.0],
            'netprofit_margin': [25.0],
            'debt_to_assets': [60.0],
            'current_ratio': [1.5],
            'quick_ratio': [1.2],
            'ocfps': [2.5],
            'eps': [1.8],
            'bps': [15.0],
        })
        source._pro.fina_indicator.return_value = raw_df

        result = source.get_financial_indicator('600000.SH')
        assert not result.empty
        assert 'roe' in result.columns

    def test_get_adj_factor(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'trade_date': ['20240102', '20240103'],
            'adj_factor': [1.0, 1.01],
        })
        source._pro.adj_factor.return_value = raw_df

        result = source.get_adj_factor('600000.SH', '2024-01-02', '2024-01-03')
        assert not result.empty
        assert 'adj_factor' in result.columns

    def test_format_date(self):
        source = self._make_source()
        assert source._format_date('2024-01-02') == '20240102'
        assert source._format_date(None) is None
        assert source._format_date('') is None

    def test_format_date_back(self):
        source = self._make_source()
        assert source._format_date_back('20240102') == '2024-01-02'
        assert source._format_date_back('2024-01-02') == '2024-01-02'  # already formatted
        assert source._format_date_back(None) is None

    def test_api_error_returns_empty(self):
        source = self._make_source()
        source._pro.daily.side_effect = Exception("API limit exceeded")
        result = source.get_stock_daily('600000.SH', '2024-01-01', '2024-01-10')
        assert result.empty


# ==================== TestAKShareDataSource ====================

class TestAKShareDataSource:
    """AKShare 数据源测试（mock API）"""

    def _make_source(self, connected=True):
        from app.data_sources.akshare_source import AKShareDataSource
        source = AKShareDataSource()
        source._connected = connected
        source._ak = MagicMock()
        return source

    def test_init(self):
        from app.data_sources.akshare_source import AKShareDataSource
        source = AKShareDataSource()
        assert source._ak is None

    def test_connect_success(self):
        from app.data_sources.akshare_source import AKShareDataSource
        with patch('akshare.stock_zh_a_hist_tx') as mock_hist:
            mock_hist.return_value = pd.DataFrame({'date': ['2024-01-02']})
            source = AKShareDataSource()
            result = source.connect()
            assert result is True

    def test_connect_failure(self):
        from app.data_sources.akshare_source import AKShareDataSource
        with patch('akshare.stock_zh_a_hist_tx') as mock_hist:
            mock_hist.side_effect = Exception("network error")
            source = AKShareDataSource()
            result = source.connect()
            assert result is False

    def test_get_stock_daily(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'date': ['2024-01-02', '2024-01-03'],
            'open': [10.0, 10.5],
            'high': [11.0, 11.0],
            'low': [9.5, 10.0],
            'close': [10.5, 10.8],
            'volume': [100000, 120000],
        })
        source._ak.stock_zh_a_hist_tx.return_value = raw_df

        result = source.get_stock_daily('600000.SH', '2024-01-02', '2024-01-03')
        assert not result.empty
        assert 'trade_date' in result.columns
        assert 'pct_chg' in result.columns

    def test_get_stock_daily_not_connected(self):
        source = self._make_source(connected=False)
        result = source.get_stock_daily('600000.SH', '2024-01-01', '2024-01-10')
        assert result.empty

    def test_get_index_daily(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'date': ['2024-01-02', '2024-01-03'],
            'open': [3000, 3010],
            'high': [3020, 3030],
            'low': [2990, 3000],
            'close': [3010, 3020],
            'volume': [1e8, 1.1e8],
        })
        source._ak.stock_zh_index_daily.return_value = raw_df

        result = source.get_index_daily('000001.SH', '2024-01-02', '2024-01-03')
        assert not result.empty
        assert 'trade_date' in result.columns

    def test_get_stock_basic(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            '代码': ['sh600000', 'sz000001'],
            '名称': ['浦发银行', '平安银行'],
        })
        source._ak.stock_zh_a_spot.return_value = raw_df

        result = source.get_stock_basic()
        assert not result.empty
        assert 'ts_code' in result.columns
        assert result['ts_code'].iloc[0] == '600000.SH'

    def test_get_trading_calendar(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'trade_date': pd.to_datetime(['2024-01-02', '2024-01-03']),
        })
        source._ak.tool_trade_date_hist_sina.return_value = raw_df

        result = source.get_trading_calendar('2024-01-02', '2024-01-03')
        assert not result.empty
        assert 'is_open' in result.columns

    def test_get_index_components(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            '成分券代码': ['600000', '000001'],
        })
        source._ak.index_stock_cons_weight_csindex.return_value = raw_df

        result = source.get_index_components('000300.SH')
        assert len(result) == 2
        assert '600000.SH' in result
        assert '000001.SZ' in result

    def test_format_code(self):
        source = self._make_source()
        assert source._format_code('600000.SH') == '600000'
        assert source._format_code('000001.SZ') == '000001'
        assert source._format_code('600000') == '600000'

    def test_format_code_back(self):
        source = self._make_source()
        assert source._format_code_back('600000') == '600000.SH'
        assert source._format_code_back('600000.SH') == '600000.SH'

    def test_api_error_returns_empty(self):
        source = self._make_source()
        source._ak.stock_zh_a_hist_tx.side_effect = Exception("API error")
        result = source.get_stock_daily('600000.SH', '2024-01-01', '2024-01-10')
        assert result.empty

    def test_get_stock_daily_batch(self):
        source = self._make_source()
        raw_df = pd.DataFrame({
            'date': ['2024-01-02'],
            'open': [10.0], 'high': [11.0], 'low': [9.5], 'close': [10.5],
            'volume': [100000],
        })
        source._ak.stock_zh_a_hist_tx.return_value = raw_df

        result = source.get_stock_daily_batch(['600000.SH'], '2024-01-02', '2024-01-02')
        assert not result.empty
        assert 'ts_code' in result.columns


# ==================== TestCrawlerDataSource ====================

class TestCrawlerDataSource:
    """爬虫数据源测试（mock requests）"""

    def _make_source(self, connected=True):
        from app.data_sources.crawler_source import CrawlerDataSource
        source = CrawlerDataSource()
        source._connected = connected
        return source

    def test_init(self):
        from app.data_sources.crawler_source import CrawlerDataSource
        source = CrawlerDataSource()
        assert source.session is not None
        assert 'User-Agent' in source.session.headers

    def test_connect_success(self):
        from app.data_sources.crawler_source import CrawlerDataSource
        source = CrawlerDataSource()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = 'var hq_str_sh000001="上证指数,3000,2990,3010,3020,2990,...";'

        with patch.object(source.session, 'get', return_value=mock_resp):
            result = source.connect()
            assert result is True

    def test_connect_failure(self):
        from app.data_sources.crawler_source import CrawlerDataSource
        source = CrawlerDataSource()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = 'Forbidden'

        with patch.object(source.session, 'get', return_value=mock_resp):
            result = source.connect()
            assert result is False

    def test_connect_exception(self):
        from app.data_sources.crawler_source import CrawlerDataSource
        source = CrawlerDataSource()
        with patch.object(source.session, 'get', side_effect=Exception("timeout")):
            result = source.connect()
            assert result is False

    def test_get_sina_code(self):
        source = self._make_source()
        assert source._get_sina_code('600000.SH') == 'sh600000'
        assert source._get_sina_code('000001.SZ') == 'sz000001'
        assert source._get_sina_code('600000') == 'sh600000'
        assert source._get_sina_code('000001') == 'sz000001'

    def test_parse_sina_quote(self):
        source = self._make_source()
        # 新浪行情格式：至少32个字段
        fields = ','.join(['浦发银行', '10.00', '9.90', '10.50', '11.00', '9.80',
                          '10.40', '10.50', '50000', '5500000.00']
                          + ['0'] * 22)  # padding to 32 fields
        text = f'var hq_str_sh600000="{fields}";'
        result = source._parse_sina_quote(text, 'sh600000')
        assert result is not None
        assert result['name'] == '浦发银行'
        assert result['open'] == 10.0
        assert result['volume'] == 50000.0

    def test_parse_sina_quote_no_match(self):
        source = self._make_source()
        result = source._parse_sina_quote('no data here', 'sh600000')
        assert result is None

    def test_get_stock_daily(self):
        source = self._make_source()
        kline_data = [
            {'day': '2024-01-02', 'open': '10.0', 'high': '11.0',
             'low': '9.5', 'close': '10.5', 'volume': '100000'},
            {'day': '2024-01-03', 'open': '10.5', 'high': '11.0',
             'low': '10.0', 'close': '10.8', 'volume': '120000'},
        ]
        mock_resp = MagicMock()
        mock_resp.text = '[{"day":"2024-01-02","open":"10.0","high":"11.0","low":"9.5","close":"10.5","volume":"100000"},{"day":"2024-01-03","open":"10.5","high":"11.0","low":"10.0","close":"10.8","volume":"120000"}]'

        with patch.object(source.session, 'get', return_value=mock_resp):
            result = source.get_stock_daily('600000.SH', '2024-01-02', '2024-01-03')
            assert not result.empty
            assert 'trade_date' in result.columns
            assert 'pct_chg' in result.columns

    def test_get_stock_daily_not_connected(self):
        source = self._make_source(connected=False)
        result = source.get_stock_daily('600000.SH', '2024-01-01', '2024-01-10')
        assert result.empty

    def test_get_realtime_quotes(self):
        source = self._make_source()
        fields = ','.join(['浦发银行', '10.00', '9.90', '10.50', '11.00', '9.80',
                          '10.40', '10.50', '50000', '5500000.00']
                          + ['0'] * 22)
        mock_resp = MagicMock()
        mock_resp.text = f'var hq_str_sh600000="{fields}";'

        with patch.object(source.session, 'get', return_value=mock_resp):
            result = source.get_realtime_quotes(['600000.SH'])
            assert not result.empty
            assert 'name' in result.columns

    def test_get_stock_basic(self):
        source = self._make_source()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'data': {
                'diff': [
                    {'f12': '600000', 'f14': '浦发银行'},
                    {'f12': '600036', 'f14': '招商银行'},
                ]
            }
        }

        with patch.object(source.session, 'get', return_value=mock_resp):
            result = source.get_stock_basic()
            assert not result.empty
            assert 'ts_code' in result.columns

    def test_financial_methods_return_empty(self):
        """爬虫源财务数据接口返回空"""
        source = self._make_source()
        assert source.get_financial_indicator('600000.SH').empty
        assert source.get_financial_data('600000.SH').empty
        assert source.get_income_statement('600000.SH').empty
        assert source.get_balance_sheet('600000.SH').empty
        assert source.get_adj_factor('600000.SH', '2024-01-01', '2024-01-10').empty


# ==================== TestDataNormalizer ====================

class TestDataNormalizer:
    """数据标准化器测试"""

    def _make_normalizer(self):
        from app.data_sources.normalizer import DataNormalizer
        return DataNormalizer()

    def test_normalize_stock_daily_tushare(self):
        normalizer = self._make_normalizer()
        df = make_stock_daily_df()
        result = normalizer.normalize_stock_daily(df, 'tushare')
        assert not result.empty
        assert 'data_source' in result.columns
        assert result['data_source'].iloc[0] == 'tushare'
        assert 'amount_is_estimated' in result.columns
        assert bool(result['amount_is_estimated'].iloc[0]) is False

    def test_normalize_stock_daily_akshare_estimated(self):
        normalizer = self._make_normalizer()
        df = make_stock_daily_df()
        result = normalizer.normalize_stock_daily(df, 'akshare')
        assert bool(result['amount_is_estimated'].iloc[0]) is True

    def test_normalize_stock_daily_crawler_estimated(self):
        normalizer = self._make_normalizer()
        df = make_stock_daily_df()
        result = normalizer.normalize_stock_daily(df, 'crawler')
        assert bool(result['amount_is_estimated'].iloc[0]) is True

    def test_normalize_stock_daily_empty(self):
        normalizer = self._make_normalizer()
        result = normalizer.normalize_stock_daily(pd.DataFrame(), 'tushare')
        assert result.empty

    def test_normalize_stock_daily_date_format(self):
        normalizer = self._make_normalizer()
        df = pd.DataFrame({
            'trade_date': ['20240102', '20240103'],
            'open': [10.0, 10.5],
            'high': [11.0, 11.0],
            'low': [9.5, 10.0],
            'close': [10.5, 10.8],
            'volume': [100000, 120000],
        })
        result = normalizer.normalize_stock_daily(df, 'tushare')
        assert result['trade_date'].iloc[0] == '2024-01-02'

    def test_normalize_stock_daily_vol_renamed(self):
        normalizer = self._make_normalizer()
        df = pd.DataFrame({
            'trade_date': ['2024-01-02'],
            'open': [10.0], 'high': [11.0], 'low': [9.5], 'close': [10.5],
            'vol': [100000], 'pre_close': [10.0],
        })
        result = normalizer.normalize_stock_daily(df, 'tushare')
        assert 'volume' in result.columns

    def test_normalize_stock_daily_change_computed(self):
        normalizer = self._make_normalizer()
        df = pd.DataFrame({
            'trade_date': ['2024-01-02'],
            'open': [10.0], 'high': [11.0], 'low': [9.5], 'close': [10.5],
            'volume': [100000], 'pre_close': [10.0],
        })
        result = normalizer.normalize_stock_daily(df, 'tushare')
        assert 'change' in result.columns
        assert result['change'].iloc[0] == pytest.approx(0.5, abs=0.01)

    def test_normalize_stock_daily_sorted(self):
        normalizer = self._make_normalizer()
        df = pd.DataFrame({
            'trade_date': ['2024-01-05', '2024-01-02', '2024-01-03'],
            'open': [10.0, 10.5, 10.8],
            'high': [11.0, 11.0, 11.2],
            'low': [9.5, 10.0, 10.5],
            'close': [10.5, 10.8, 11.0],
            'volume': [100000, 120000, 110000],
        })
        result = normalizer.normalize_stock_daily(df, 'tushare')
        assert result['trade_date'].iloc[0] == '2024-01-02'

    def test_normalize_stock_daily_with_ts_code(self):
        normalizer = self._make_normalizer()
        df = make_stock_daily_df(ts_code='600000.SH')
        result = normalizer.normalize_stock_daily(df, 'tushare')
        assert 'ts_code' in result.columns

    def test_normalize_index_daily(self):
        normalizer = self._make_normalizer()
        df = make_index_daily_df()
        result = normalizer.normalize_index_daily(df, 'tushare')
        assert not result.empty
        assert 'data_source' in result.columns

    def test_normalize_index_daily_with_index_code(self):
        normalizer = self._make_normalizer()
        df = make_index_daily_df()
        df['index_code'] = '000001.SH'
        result = normalizer.normalize_index_daily(df, 'tushare')
        assert 'index_code' in result.columns

    def test_normalize_stock_basic(self):
        normalizer = self._make_normalizer()
        df = make_stock_basic_df()
        result = normalizer.normalize_stock_basic(df, 'tushare')
        assert not result.empty
        assert 'ts_code' in result.columns
        # ts_code should be uppercased
        assert result['ts_code'].iloc[0] == '600000.SH'

    def test_normalize_stock_basic_empty(self):
        normalizer = self._make_normalizer()
        result = normalizer.normalize_stock_basic(pd.DataFrame(), 'tushare')
        assert result.empty

    def test_normalize_trading_calendar(self):
        normalizer = self._make_normalizer()
        df = make_trading_calendar_df()
        result = normalizer.normalize_trading_calendar(df, 'tushare')
        assert not result.empty
        assert 'is_open' in result.columns
        assert result['is_open'].dtype == int

    def test_normalize_trading_calendar_date_format(self):
        normalizer = self._make_normalizer()
        df = pd.DataFrame({
            'cal_date': ['20240102', '20240103'],
            'is_open': [1, 1],
        })
        result = normalizer.normalize_trading_calendar(df, 'tushare')
        assert result['trade_date'].iloc[0] == '2024-01-02'

    def test_normalize_date_column_yyyymmdd(self):
        normalizer = self._make_normalizer()
        series = pd.Series(['20240102', '20240103'])
        result = normalizer._normalize_date_column(series)
        assert result.iloc[0] == '2024-01-02'

    def test_normalize_date_column_iso(self):
        normalizer = self._make_normalizer()
        series = pd.Series(['2024-01-02', '2024-01-03'])
        result = normalizer._normalize_date_column(series)
        assert result.iloc[0] == '2024-01-02'

    def test_normalize_date_column_empty(self):
        normalizer = self._make_normalizer()
        series = pd.Series([], dtype=object)
        result = normalizer._normalize_date_column(series)
        assert result.empty


# ==================== TestDataCleaner ====================

class TestDataCleaner:
    """数据清洗器测试"""

    def _make_cleaner(self):
        from app.data_sources.cleaner import DataCleaner
        return DataCleaner()

    def test_clean_stock_daily_normal(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH'] * 5,
            'trade_date': ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-01-08'],
            'open': [10.0, 10.5, 10.8, 11.0, 10.5],
            'high': [11.0, 11.0, 11.2, 11.5, 11.0],
            'low': [9.5, 10.0, 10.5, 10.8, 10.0],
            'close': [10.5, 10.8, 11.0, 10.5, 10.5],
            'pre_close': [10.0, 10.5, 10.8, 11.0, 10.5],
            'volume': [100000, 120000, 110000, 130000, 100000],
            'amount': [1e6, 1.2e6, 1.1e6, 1.3e6, 1e6],
            'pct_chg': [5.0, 2.86, 1.85, -4.55, 0.0],
        })
        result, report = cleaner.clean_stock_daily(df)
        assert report.original_count == 5
        assert report.cleaned_count == 5
        assert report.removed_count == 0

    def test_clean_stock_daily_missing_critical(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH', '600000.SH'],
            'trade_date': ['2024-01-02', '2024-01-03'],
            'open': [10.0, np.nan],
            'high': [11.0, 11.0],
            'low': [9.5, 10.0],
            'close': [10.5, np.nan],  # close is critical
            'volume': [100000, 120000],
        })
        result, report = cleaner.clean_stock_daily(df)
        assert report.removed_count >= 1

    def test_clean_stock_daily_negative_values(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH', '600000.SH'],
            'trade_date': ['2024-01-02', '2024-01-03'],
            'open': [10.0, -1.0],  # negative
            'high': [11.0, 11.0],
            'low': [9.5, 10.0],
            'close': [10.5, 10.8],
            'volume': [100000, 120000],
        })
        result, report = cleaner.clean_stock_daily(df)
        assert report.removed_count >= 1

    def test_clean_stock_daily_ohlc_violation(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH'],
            'trade_date': ['2024-01-02'],
            'open': [10.0],
            'high': [9.0],  # high < open → violation
            'low': [8.0],
            'close': [8.5],
            'volume': [100000],
        })
        result, report = cleaner.clean_stock_daily(df)
        assert report.flagged_count >= 1
        assert 'ohlc_flag' in result.columns

    def test_clean_stock_daily_limit_violation_mainboard(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH'],
            'trade_date': ['2024-01-02'],
            'open': [10.0],
            'high': [12.0],
            'low': [9.5],
            'close': [11.5],
            'volume': [100000],
            'pct_chg': [15.0],  # > 10% + 0.5% tolerance
        })
        result, report = cleaner.clean_stock_daily(df)
        assert report.flagged_count >= 1

    def test_clean_stock_daily_limit_violation_gem(self):
        """创业板涨跌停阈值为 20%"""
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['300001.SZ'],
            'trade_date': ['2024-01-02'],
            'open': [10.0],
            'high': [12.5],
            'low': [9.5],
            'close': [12.0],
            'volume': [100000],
            'pct_chg': [15.0],  # < 20% + 0.5%, should NOT be flagged
        })
        result, report = cleaner.clean_stock_daily(df)
        # 15% is within GEM limit (20% + 0.5% tolerance)
        limit_flagged = result.get('limit_flag', pd.Series([False])).sum()
        assert limit_flagged == 0

    def test_clean_stock_daily_suspended(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH', '600000.SH'],
            'trade_date': ['2024-01-02', '2024-01-03'],
            'open': [10.0, 10.5],
            'high': [11.0, 10.5],
            'low': [9.5, 10.5],
            'close': [10.5, 10.5],
            'pre_close': [10.0, 10.5],
            'volume': [100000, 0],  # second row: suspended
        })
        result, report = cleaner.clean_stock_daily(df)
        assert 'is_suspended' in result.columns
        assert result['is_suspended'].sum() == 1

    def test_clean_stock_daily_deduplicate(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH', '600000.SH'],
            'trade_date': ['2024-01-02', '2024-01-02'],  # duplicate
            'open': [10.0, 10.1],
            'high': [11.0, 11.1],
            'low': [9.5, 9.6],
            'close': [10.5, 10.6],
            'volume': [100000, 110000],
        })
        result, report = cleaner.clean_stock_daily(df)
        assert len(result) == 1
        assert report.removed_count >= 1

    def test_clean_stock_daily_fill_non_critical(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH', '600000.SH'],
            'trade_date': ['2024-01-02', '2024-01-03'],
            'open': [10.0, np.nan],  # non-critical, should be filled
            'high': [11.0, 11.0],
            'low': [9.5, 10.0],
            'close': [10.5, 10.8],
            'pre_close': [10.0, 10.5],
            'volume': [100000, 120000],
        })
        result, report = cleaner.clean_stock_daily(df)
        # open should be forward-filled
        assert not result['open'].isna().any()

    def test_clean_stock_daily_empty(self):
        cleaner = self._make_cleaner()
        result, report = cleaner.clean_stock_daily(pd.DataFrame())
        assert result.empty
        assert report.original_count == 0

    def test_clean_index_daily(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'index_code': ['000001.SH'] * 3,
            'trade_date': ['2024-01-02', '2024-01-03', '2024-01-04'],
            'open': [3000, 3010, 3020],
            'high': [3020, 3030, 3040],
            'low': [2990, 3000, 3010],
            'close': [3010, 3020, 3030],
            'volume': [1e8, 1.1e8, 1.2e8],
        })
        result, report = cleaner.clean_index_daily(df)
        assert report.cleaned_count == 3

    def test_clean_stock_basic(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH', '000001.SZ', '830001.BJ'],
            'symbol': ['600000', '000001', '830001'],
            'name': ['浦发银行', '平安银行', '北交所股票'],
            'industry': ['银行', None, '其他'],
            'market': ['主板', '主板', '北交所'],
            'list_date': ['19991110', '19910403', '20200101'],
            'status': ['L', 'L', 'L'],
        })
        result, report = cleaner.clean_stock_basic(df)
        # 北交所股票应该被过滤
        assert not result['ts_code'].str.startswith('8').any()
        # industry 缺失应填充
        assert not result['industry'].isna().any()

    def test_clean_stock_basic_invalid_ts_code(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['INVALID', '600000.SH'],
            'symbol': ['INVALID', '600000'],
            'name': ['无效', '浦发银行'],
            'industry': ['其他', '银行'],
            'market': ['其他', '主板'],
            'list_date': [None, '19991110'],
            'status': ['L', 'L'],
        })
        result, report = cleaner.clean_stock_basic(df)
        assert len(result) == 1
        assert result['ts_code'].iloc[0] == '600000.SH'

    def test_clean_stock_basic_deduplicate(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'ts_code': ['600000.SH', '600000.SH'],
            'symbol': ['600000', '600000'],
            'name': ['浦发银行', '浦发银行2'],
            'industry': ['银行', '银行'],
            'market': ['主板', '主板'],
            'list_date': ['19991110', '19991110'],
            'status': ['L', 'L'],
        })
        result, report = cleaner.clean_stock_basic(df)
        assert len(result) == 1

    def test_clean_trading_calendar(self):
        cleaner = self._make_cleaner()
        df = pd.DataFrame({
            'trade_date': ['2024-01-02', '2024-01-03', '2024-01-02'],  # duplicate
            'is_open': [1, 1, 1],
        })
        result, report = cleaner.clean_trading_calendar(df)
        assert len(result) == 2
        assert report.removed_count >= 1

    def test_clean_report_summary(self):
        from app.data_sources.cleaner import CleanReport
        report = CleanReport(original_count=100, cleaned_count=95, removed_count=5)
        summary = report.summary()
        assert '100' in summary
        assert '95' in summary
        assert '5' in summary

    def test_clean_report_add_issue(self):
        from app.data_sources.cleaner import CleanReport
        report = CleanReport()
        report.add_issue('test_issue', 'test message', code='600000.SH', trade_date='2024-01-02')
        assert len(report.issues) == 1
        assert report.issues[0]['type'] == 'test_issue'
        assert report.issues[0]['ts_code'] == '600000.SH'


# ==================== TestModuleImports ====================

class TestModuleImports:
    """模块导入测试"""

    def test_import_data_sources(self):
        from app.data_sources import (
            BaseDataSource, DataSourceManager, TushareDataSource,
            AKShareDataSource, CrawlerDataSource, DataNormalizer,
            DataCleaner, CleanReport, data_source_manager, get_data_source,
        )
        assert BaseDataSource is not None
        assert DataSourceManager is not None

    def test_get_data_source(self):
        from app.data_sources.base import get_data_source
        # Initially no sources registered
        result = get_data_source('nonexistent')
        assert result is None
