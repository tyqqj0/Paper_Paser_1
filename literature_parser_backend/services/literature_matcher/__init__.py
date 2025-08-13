"""
Literature Matcher Service

Unified literature matching service for deduplication and citation resolution.
Provides pluggable matching strategies and configurable thresholds.
"""

from .base_matcher import LiteratureMatcher, MatchType, MatchResult
from .exact_matcher import ExactMatcher
from .fuzzy_matcher import FuzzyMatcher

__all__ = [
    "LiteratureMatcher",
    "MatchType", 
    "MatchResult",
    "ExactMatcher",
    "FuzzyMatcher",
]

