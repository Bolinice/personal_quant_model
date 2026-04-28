"""
数据源模块
支持 Tushare、AKShare 和爬虫多数据源
"""

from app.data_sources.akshare_source import AKShareSource
from app.data_sources.base import BaseDataSource, DataSourceManager, data_source_manager, get_data_source
from app.data_sources.cleaner import CleanReport, DataCleaner
from app.data_sources.crawler_source import CrawlerDataSource
from app.data_sources.normalizer import DataNormalizer
from app.data_sources.tushare_source import TushareSource

__all__ = [
    "AKShareSource",
    "BaseDataSource",
    "CleanReport",
    "CrawlerDataSource",
    "DataCleaner",
    "DataNormalizer",
    "DataSourceManager",
    "TushareSource",
    "data_source_manager",
    "get_data_source",
]
