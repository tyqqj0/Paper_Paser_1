"""
Metadata fetching framework with unified processor architecture.

This module provides a modular, extensible framework for fetching literature metadata
from various sources using a standardized interface.
"""

from .fetcher import MetadataFetcher
from .base import MetadataProcessor, ProcessorResult
from .registry import ProcessorRegistry

__all__ = [
    "MetadataFetcher",
    "MetadataProcessor", 
    "ProcessorResult",
    "ProcessorRegistry"
]
