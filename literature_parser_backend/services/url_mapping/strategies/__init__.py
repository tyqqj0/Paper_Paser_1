"""
URL映射策略模块

包含各种标识符提取策略的实现。
"""

from .regex_strategy import RegexStrategy
from .scraping_strategy import ScrapingStrategy
from .database_strategy import DatabaseStrategy
from .api_strategy import APIStrategy

__all__ = [
    "RegexStrategy",
    "ScrapingStrategy", 
    "DatabaseStrategy",
    "APIStrategy",
]
