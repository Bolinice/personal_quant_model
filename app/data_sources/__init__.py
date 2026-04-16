"""
数据源模块
支持 Tushare、AKShare 和爬虫多数据源
"""
from app.data_sources.base import BaseDataSource, DataSourceManager, data_source_manager, get_data_source
from app.data_sources.tushare_source import TushareDataSource
from app.data_sources.akshare_source import AKShareDataSource
from app.data_sources.crawler_source import CrawlerDataSource

__all__ = [
    'BaseDataSource',
    'DataSourceManager',
    'TushareDataSource',
    'AKShareDataSource',
    'CrawlerDataSource',
    'data_source_manager',
    'get_data_source',
]
