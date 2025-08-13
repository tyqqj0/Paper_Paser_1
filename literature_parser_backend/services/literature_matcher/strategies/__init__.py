"""
Literature Matching Strategies

Collection of specific matching strategies for different data fields.
"""

from .doi_strategy import DOIStrategy
from .title_strategy import TitleStrategy
from .author_strategy import AuthorStrategy
from .year_strategy import YearStrategy

__all__ = [
    "DOIStrategy",
    "TitleStrategy", 
    "AuthorStrategy",
    "YearStrategy",
]

